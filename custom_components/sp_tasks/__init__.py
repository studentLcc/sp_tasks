from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_DATE, ATTR_LAST_SYNC, ATTR_TASKS, DOMAIN, STORAGE_KEY, STORAGE_VERSION

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
SERVICE_GET_TASKS = "get_tasks"


class TasksView(HomeAssistantView):
    """Authenticated endpoint used by the bridge running beside Super Productivity."""

    url = "/api/sp_tasks/tasks"
    name = "api:sp_tasks:tasks"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        task_date = request.query.get(ATTR_DATE)
        stored = _snapshot(hass, task_date)
        return web.json_response(stored)

    async def post(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        try:
            payload = await request.json()
        except (TypeError, ValueError) as error:
            raise web.HTTPBadRequest(text=f"invalid JSON: {error}") from error
        if not isinstance(payload, dict) or not isinstance(payload.get(ATTR_TASKS), list):
            raise web.HTTPBadRequest(text="payload must contain a tasks list")
        task_date = str(payload.get(ATTR_DATE) or "latest")
        tasks = [task for task in payload[ATTR_TASKS] if isinstance(task, dict)]
        groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
        message = payload.get("message") if isinstance(payload.get("message"), str) else ""
        normalized = {
            ATTR_DATE: task_date,
            ATTR_TASKS: tasks,
            "groups": groups,
            "message": message,
            ATTR_LAST_SYNC: payload.get("synced_at") or datetime.now(timezone.utc).isoformat(),
        }
        data = hass.data[DOMAIN]
        data["latest"] = normalized
        data["tasks_by_date"][task_date] = normalized
        await data["store"].async_save({"latest": normalized, "tasks_by_date": data["tasks_by_date"]})
        for entity in data["entities"]:
            entity.async_write_ha_state()
        return web.json_response({"ok": True, "date": task_date, "task_count": len(tasks)})


def _snapshot(hass: HomeAssistant, task_date: str | None = None) -> dict[str, Any]:
    data = hass.data[DOMAIN]
    if task_date and task_date in data["tasks_by_date"]:
        return data["tasks_by_date"][task_date]
    if data.get("latest"):
        return data["latest"]
    by_date = data["tasks_by_date"]
    if not by_date:
        return {ATTR_DATE: task_date, ATTR_TASKS: [], "message": ""}
    return by_date[max(by_date)]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if DOMAIN not in hass.data:
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        stored = await store.async_load() or {}
        hass.data[DOMAIN] = {
            "store": store,
            "latest": stored.get("latest"),
            "tasks_by_date": stored.get("tasks_by_date", {}),
            "entities": [],
        }
        hass.http.register_view(TasksView)
        _register_get_tasks(hass)
    return True


def _register_get_tasks(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_GET_TASKS):
        return
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TASKS,
        _async_get_tasks,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}, extra=vol.ALLOW_EXTRA),
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_get_tasks(call: ServiceCall) -> dict[str, Any]:
    """Return saved tasks for an automation response_variable."""
    stored = _snapshot(call.hass)
    groups = stored.get("groups") if isinstance(stored.get("groups"), dict) else {}
    return {
        "date": stored.get(ATTR_DATE),
        "last_sync": stored.get(ATTR_LAST_SYNC),
        "overdue": list(groups.get("overdue") or []),
        "today": list(groups.get("today") or []),
        "week": list(groups.get("week") or []),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _register_get_tasks(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
