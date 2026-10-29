from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .util import serverchan_url


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional("wecom_webhook_url", default=defaults.get("wecom_webhook_url", "")): cv.string,
            vol.Optional("serverchan_sendkey", default=defaults.get("serverchan_sendkey", "")): cv.string,
            vol.Optional("serverchan_uid", default=defaults.get("serverchan_uid", "")): cv.string,
        }
    )


def _validate(user_input: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    data = {
        "wecom_webhook_url": str(user_input.get("wecom_webhook_url") or "").strip(),
        "serverchan_sendkey": str(user_input.get("serverchan_sendkey") or "").strip(),
        "serverchan_uid": str(user_input.get("serverchan_uid") or "").strip(),
    }
    errors: dict[str, str] = {}
    if data["wecom_webhook_url"] and not data["wecom_webhook_url"].startswith("https://"):
        errors["wecom_webhook_url"] = "invalid_url"
    if data["serverchan_sendkey"]:
        try:
            serverchan_url(data["serverchan_sendkey"], data["serverchan_uid"])
        except ValueError:
            errors["serverchan_sendkey"] = "invalid_sendkey"
    return data, errors


class SpTasksConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="Super Productivity 任务", data=data)
            user_input = data
        return self.async_show_form(step_id="user", data_schema=_schema(user_input), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SpTasksOptionsFlow:
        return SpTasksOptionsFlow()


class SpTasksOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=data)
            current = data
        else:
            current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current), errors=errors)
