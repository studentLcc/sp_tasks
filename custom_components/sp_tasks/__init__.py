from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import voluptuous as vol
from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_DATE,
    ATTR_LAST_SYNC,
    ATTR_TASKS,
    DOMAIN,
    SERVICE_SEND_DAILY_SUMMARY,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .util import clean_text, format_markdown, serverchan_url

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DATE): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("wecom_webhook_url"): cv.string,
        vol.Optional("serverchan_sendkey"): cv.string,
        vol.Optional("serverchan_uid"): cv.string,
    }
)


def _today() -> str:
    return dt_util.now().date().isoformat()


def notification_config(hass: HomeAssistant) -> dict[str, Any]:
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return {}
    entry = entries[0]
    return {**entry.data, **entry.options}


async def _post_json(hass: HomeAssistant, url: str, payload: dict[str, Any]) -> Any:
    session = async_get_clientsession(hass)
    async with session.post(url, json=payload, timeout=20) as response:
        response.raise_for_status()
        try:
            return await response.json()
        except (TypeError, ValueError):
            return {"status": response.status}


async def _send_daily_summary(hass: HomeAssistant, call: ServiceCall) -> None:
    task_date = call.data.get(ATTR_DATE, _today())
    stored = hass.data[DOMAIN]["tasks_by_date"].get(task_date, {ATTR_TASKS: []})
    title = call.data.get("title", f"今日任务（{task_date}）")
    markdown = format_markdown(stored, task_date)
    config = notification_config(hass)
    results: dict[str, Any] = {}
    wecom_url = clean_text(call.data.get("wecom_webhook_url")) or clean_text(config.get("wecom_webhook_url"))
    if wecom_url:
        results["wecom"] = await _post_json(
            hass, wecom_url, {"msgtype": "markdown", "markdown": {"content": markdown}}
        )
    sendkey = clean_text(call.data.get("serverchan_sendkey")) or clean_text(config.get("serverchan_sendkey"))
    if sendkey:
        uid = clean_text(call.data.get("serverchan_uid")) or clean_text(config.get("serverchan_uid"))
        results["serverchan"] = await _post_json(hass, serverchan_url(sendkey, uid), {"title": title, "desp": markdown})
    if not results:
        raise HomeAssistantError("未配置企业微信 webhook 或 Server酱³ SendKey")
    hass.bus.async_fire(f"{DOMAIN}_summary_sent", {"date": task_date, "results": results})


async def _handle_send_daily_summary(call: ServiceCall) -> None:
    await _send_daily_summary(call.hass, call)


class TasksView(HomeAssistantView):
    """Authenticated endpoint used by the bridge running beside Super Productivity."""

    url = "/api/sp_tasks/tasks"
    name = "api:sp_tasks:tasks"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        task_date = request.query.get(ATTR_DATE, _today())
        stored = hass.data[DOMAIN]["tasks_by_date"].get(task_date, {ATTR_DATE: task_date, ATTR_TASKS: []})
        return web.json_response(stored)

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            payload = await request.json()
        except (TypeError, ValueError) as error:
            raise web.HTTPBadRequest(text=f"invalid JSON: {error}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get(ATTR_TASKS), list):
            raise web.HTTPBadRequest(text="payload must contain a tasks list")
        task_date = str(payload.get(ATTR_DATE) or _today())
        tasks = [task for task in payload[ATTR_TASKS] if isinstance(task, dict)]
        normalized = {
            ATTR_DATE: task_date,
            ATTR_TASKS: tasks,
            ATTR_LAST_SYNC: payload.get("synced_at") or datetime.now(timezone.utc).isoformat(),
        }
        data = hass.data[DOMAIN]
        data["tasks_by_date"][task_date] = normalized
        await data["store"].async_save({"tasks_by_date": data["tasks_by_date"]})
        for entity in data["entities"]:
            entity.async_write_ha_state()
        return web.json_response({"ok": True, "date": task_date, "task_count": len(tasks)})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if DOMAIN not in hass.data:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {}
        hass.data[DOMAIN] = {
            "store": store,
            "tasks_by_date": stored.get("tasks_by_date", {}),
            "entities": [],
        }
        hass.http.register_view(TasksView)
        hass.services.async_register(
            DOMAIN,
            SERVICE_SEND_DAILY_SUMMARY,
            _handle_send_daily_summary,
            schema=SERVICE_SCHEMA,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
