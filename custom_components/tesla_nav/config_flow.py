from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PROXY_URL,
    CONF_REFRESH_TOKEN,
    CONF_ROUTES,
    DEFAULT_PROXY_URL,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_REFRESH_TOKEN): str,
        vol.Optional(CONF_PROXY_URL, default=DEFAULT_PROXY_URL): str,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TeslaNavOptionsFlow(config_entry)


class TeslaNavOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._routes: list[dict] = list(config_entry.options.get(CONF_ROUTES, []))

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_route", "remove_route", "finish"],
        )

    async def async_step_add_route(self, user_input=None):
        errors = {}
        if user_input is not None:
            waypoints = _parse_waypoints(user_input["waypoints"])
            if not waypoints:
                errors["waypoints"] = "invalid_waypoints"
            else:
                self._routes.append(
                    {
                        "name": user_input["name"],
                        "weekday": user_input["weekday"],
                        "time": user_input["time"],
                        "waypoints": waypoints,
                    }
                )
                return await self.async_step_init()

        return self.async_show_form(
            step_id="add_route",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("weekday"): vol.In(
                        ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    ),
                    vol.Required("time"): str,
                    vol.Required("waypoints"): str,
                }
            ),
            description_placeholders={
                "waypoints_help": "One per line: Label | ChIJxxxxxxx"
            },
            errors=errors,
        )

    async def async_step_remove_route(self, user_input=None):
        if not self._routes:
            return await self.async_step_init()

        if user_input is not None:
            names_to_remove = set(user_input.get("routes", []))
            self._routes = [r for r in self._routes if r["name"] not in names_to_remove]
            return await self.async_step_init()

        return self.async_show_form(
            step_id="remove_route",
            data_schema=vol.Schema(
                {
                    vol.Required("routes"): vol.All(
                        [vol.In([r["name"] for r in self._routes])],
                    )
                }
            ),
        )

    async def async_step_finish(self, user_input=None):
        return self.async_create_entry(data={CONF_ROUTES: self._routes})


def _parse_waypoints(text: str) -> list[dict]:
    result = []
    for line in text.strip().splitlines():
        if "|" in line:
            label, place_id = line.split("|", 1)
            label, place_id = label.strip(), place_id.strip()
            if label and place_id:
                result.append({"label": label, "place_id": place_id})
    return result
