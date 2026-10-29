from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "tasks")},
            name="Super Productivity 任务",
            manufacturer="Super Productivity",
        )

    @property
    def _today_data(self) -> dict[str, Any]:
        return self.hass.data[DOMAIN]["tasks_by_date"].get(dt_util.now().date().isoformat(), {})

    @property
    def native_value(self) -> int:
        return len(self._today_data.get(ATTR_TASKS, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._today_data
        return {
            ATTR_DATE: data.get(ATTR_DATE, dt_util.now().date().isoformat()),
            ATTR_TASKS: data.get(ATTR_TASKS, []),
            ATTR_LAST_SYNC: data.get(ATTR_LAST_SYNC),
        }
