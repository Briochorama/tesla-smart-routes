from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ROUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    routes = entry.options.get(CONF_ROUTES, [])
    async_add_entities(TeslaRouteButton(entry, route) for route in routes)


class TeslaRouteButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, route: dict) -> None:
        self._entry = entry
        self._route = route
        self._attr_unique_id = f"{entry.entry_id}_{route['name']}"
        self._attr_name = route["name"]

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "weekday": self._route["weekday"],
            "time": self._route["time"],
            "waypoints_count": len(self._route["waypoints"]),
        }

    async def async_press(self) -> None:
        _LOGGER.info(
            "[tesla_nav] Would send route '%s' (%s %s) — proxy not wired yet",
            self._route["name"],
            self._route["weekday"],
            self._route["time"],
        )
