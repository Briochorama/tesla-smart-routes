from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_NAME, CONF_TIME, CONF_WAYPOINTS, CONF_WEEKDAY, SUBENTRY_TYPE_ROUTE
from .helpers import build_maps_url

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        TeslaRouteButton(entry, subentry)
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_ROUTE
    )


class TeslaRouteButton(ButtonEntity):
    def __init__(self, entry: ConfigEntry, subentry) -> None:
        self._entry = entry
        self._subentry = subentry
        self._attr_unique_id = subentry.subentry_id
        self._attr_name = subentry.data[CONF_NAME]

    @property
    def extra_state_attributes(self) -> dict:
        waypoints = self._subentry.data.get(CONF_WAYPOINTS, [])
        return {
            "weekdays": self._subentry.data[CONF_WEEKDAY],
            "time": self._subentry.data[CONF_TIME],
            "waypoints_count": len(waypoints),
            "maps_url": build_maps_url(waypoints),
        }

    async def async_press(self) -> None:
        _LOGGER.info(
            "[tesla_nav] Would send route '%s' (%s %s) — proxy not wired yet",
            self._subentry.data[CONF_NAME],
            self._subentry.data[CONF_WEEKDAY],
            self._subentry.data[CONF_TIME],
        )
