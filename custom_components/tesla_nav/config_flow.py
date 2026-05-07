from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LABEL,
    CONF_NAME,
    CONF_PLACE_ID,
    CONF_PROXY_URL,
    CONF_REFRESH_TOKEN,
    CONF_TIME,
    CONF_WAYPOINTS,
    CONF_WEEKDAY,
    DEFAULT_PROXY_URL,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Optional(CONF_PROXY_URL, default=DEFAULT_PROXY_URL): str,
    }
)

WEEKDAY_OPTIONS = [
    {"value": "monday", "label": "Monday"},
    {"value": "tuesday", "label": "Tuesday"},
    {"value": "wednesday", "label": "Wednesday"},
    {"value": "thursday", "label": "Thursday"},
    {"value": "friday", "label": "Friday"},
    {"value": "saturday", "label": "Saturday"},
    {"value": "sunday", "label": "Sunday"},
]

ROUTE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_WEEKDAY): SelectSelector(
            SelectSelectorConfig(
                options=WEEKDAY_OPTIONS,
                multiple=True,
                mode=SelectSelectorMode.LIST,
            )
        ),
        vol.Required(CONF_TIME): str,
    }
)

WAYPOINT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LABEL, default=""): str,
        vol.Optional(CONF_PLACE_ID, default=""): str,
    }
)


class TeslaNavConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="Tesla Nav", data=user_input)

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ROUTE: TeslaNavRouteSubentryFlow}


class TeslaNavRouteSubentryFlow(ConfigSubentryFlow):
    def __init__(self) -> None:
        self._route_data: dict = {}
        self._waypoints: list[dict] = []

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._route_data = user_input
            self._waypoints = []
            return await self.async_step_add_waypoint()
        return self.async_show_form(step_id="user", data_schema=ROUTE_SCHEMA)

    async def async_step_add_waypoint(self, user_input=None):
        errors = {}
        if user_input is not None:
            label = user_input.get(CONF_LABEL, "").strip()
            place_id = user_input.get(CONF_PLACE_ID, "").strip()

            if not label and not place_id:
                return self.async_create_entry(
                    title=self._route_data[CONF_NAME],
                    data={**self._route_data, CONF_WAYPOINTS: self._waypoints},
                )
            elif label and place_id:
                self._waypoints.append({"label": label, "place_id": place_id})
                return await self.async_step_add_waypoint()
            else:
                errors["base"] = "waypoint_incomplete"

        added = "\n".join(f"• {w['label']} ({w['place_id']})" for w in self._waypoints)
        return self.async_show_form(
            step_id="add_waypoint",
            data_schema=WAYPOINT_SCHEMA,
            description_placeholders={
                "waypoints": added or "None yet — leave both fields empty to finish.",
            },
            errors=errors,
        )
