from __future__ import annotations

import asyncio
import logging

import aiohttp
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_NAME,
    CONF_PROXY_URL,
    CONF_VIN,
    CONF_VIN_ENTITY,
    CONF_VIN_SOURCE,
    CONF_WAYPOINTS,
    DOMAIN,
    FLEET_API_BASE,
    SUBENTRY_TYPE_ROUTE,
    WAKE_POLL_INTERVAL,
    WAKE_RETRY_INTERVAL,
    WAKE_TIMEOUT,
)
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
        vin_source = self._subentry.data.get(CONF_VIN_SOURCE)
        vin = (
            self._subentry.data.get(CONF_VIN_ENTITY)
            if vin_source == "entity"
            else self._subentry.data.get(CONF_VIN)
        )
        return {
            "vin_source": vin_source,
            "vin": vin,
            "waypoints_count": len(waypoints),
            "maps_url": build_maps_url(waypoints),
        }

    async def _wake_vehicle(self, vin: str, headers: dict) -> bool:
        http_session = async_get_clientsession(self.hass)

        async def _send_wake() -> str | None:
            """Send wake_up. Returns 'online', 'waking', or None (offline/error)."""
            try:
                async with http_session.post(
                    f"{FLEET_API_BASE}/api/1/vehicles/{vin}/wake_up",
                    headers=headers,
                ) as resp:
                    if resp.status == 408:
                        _LOGGER.error("[tesla_nav] %s is offline (no cellular) — cannot wake", vin)
                        return None
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("response", {}).get("state", "waking")
            except aiohttp.ClientError as err:
                _LOGGER.error("[tesla_nav] wake_up request failed: %s", err)
            return None

        state = await _send_wake()
        if state is None:
            return False
        if state == "online":
            _LOGGER.info("[tesla_nav] %s already online", vin)
            return True

        _LOGGER.info("[tesla_nav] Waking %s (state: %s)...", vin, state)
        elapsed = 0
        next_retry = WAKE_RETRY_INTERVAL
        while elapsed < WAKE_TIMEOUT:
            await asyncio.sleep(WAKE_POLL_INTERVAL)
            elapsed += WAKE_POLL_INTERVAL

            if elapsed >= next_retry:
                _LOGGER.debug("[tesla_nav] Re-sending wake_up to %s", vin)
                await _send_wake()
                next_retry += WAKE_RETRY_INTERVAL

            try:
                async with http_session.get(
                    f"{FLEET_API_BASE}/api/1/vehicles/{vin}",
                    headers=headers,
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        state = data.get("response", {}).get("state")
                        _LOGGER.info("[tesla_nav] %s state: %s (%ds)", vin, state, elapsed)
                        if state == "online":
                            return True
            except aiohttp.ClientError:
                pass

        _LOGGER.error("[tesla_nav] %s did not come online within %ds", vin, WAKE_TIMEOUT)
        return False

    async def async_press(self) -> None:
        data = self._subentry.data
        name = data[CONF_NAME]

        # Resolve VIN
        if data.get(CONF_VIN_SOURCE) == "entity":
            state = self.hass.states.get(data[CONF_VIN_ENTITY])
            if state is None:
                _LOGGER.error("[tesla_nav] VIN entity %s not found", data[CONF_VIN_ENTITY])
                return
            vin = state.state
        else:
            vin = data[CONF_VIN]

        # Get fresh access token (auto-refreshes if expired)
        impl = self.hass.data[DOMAIN][self._entry.entry_id]["impl"]
        oauth_session = OAuth2Session(self.hass, self._entry, impl)
        await oauth_session.async_ensure_token_valid()
        access_token = oauth_session.token["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}
        if not await self._wake_vehicle(vin, headers):
            _LOGGER.error("[tesla_nav] Aborting route '%s' — vehicle offline", name)
            return
        _LOGGER.info("[tesla_nav] %s is online, sending route '%s'", vin, name)

        # Build waypoints string using Place IDs
        waypoints = data.get(CONF_WAYPOINTS, [])
        waypoints_str = ",".join(f"refId:{w['place_id']}" for w in waypoints)

        proxy_url = self._entry.data[CONF_PROXY_URL]
        url = f"{proxy_url}/api/1/vehicles/{vin}/command/navigation_waypoints_request"

        http_session = async_get_clientsession(self.hass)
        try:
            async with http_session.post(
                url,
                json={"waypoints": waypoints_str},
                headers=headers,
                ssl=False,  # local proxy uses self-signed cert
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
                _LOGGER.info("[tesla_nav] Route '%s' → %s: %s", name, vin, result)
        except aiohttp.ClientError as err:
            _LOGGER.error("[tesla_nav] Route '%s' failed: %s", name, err)
