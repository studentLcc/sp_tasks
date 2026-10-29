from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import ATTR_DATE, ATTR_LAST_SYNC, ATTR_TASKS, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entity = SpTasksTodaySensor(hass)
    hass.data[DOMAIN]["entities"] = [entity]
    async_add_entities([entity])


class SpTasksTodaySensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "今日任务"
    _attr_unique_id = "sp_tasks_today"
    _attr_icon = "mdi:format-list-checks"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.entity_id = "sensor.sp_tasks_today"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "tasks")},
            name="Super Productivity 任务",
            manufacturer="Super Productivity",
        )

    @property
    def _snapshot(self) -> dict[str, Any]:
        data = self.hass.data[DOMAIN]
        if data.get("latest"):
            return data["latest"]
        by_date = data.get("tasks_by_date") or {}
        if not by_date:
            return {}
        return by_date[max(by_date)]

    @property
    def native_value(self) -> int:
        return len(self._snapshot.get(ATTR_TASKS, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._snapshot
        tasks = data.get(ATTR_TASKS) or []
        groups = data.get("groups") if isinstance(data.get("groups"), dict) else {}
        message = data.get("message") if isinstance(data.get("message"), str) else ""
        if not message:
            message = "\n\n".join(f"- {task.get('title')}" for task in tasks if task.get("title"))
        if not message:
            message = "尚未同步到任务。"
        return {
            ATTR_DATE: data.get(ATTR_DATE),
            ATTR_TASKS: tasks,
            "groups": groups,
            "message": message,
            "desp": message,
            "overdue_count": len(groups.get("overdue") or []),
            "today_count": len(groups.get("today") or []),
            "week_count": len(groups.get("week") or []),
            ATTR_LAST_SYNC: data.get(ATTR_LAST_SYNC),
        }
