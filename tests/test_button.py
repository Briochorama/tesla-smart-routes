import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tesla_nav.const import CONF_ROUTES, DOMAIN


async def _setup_entry(hass: HomeAssistant, routes=None) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "client_id": "cid",
            "client_secret": "csec",
            "refresh_token": "rtok",
            "proxy_url": "https://localhost:4443",
        },
        options={CONF_ROUTES: routes or []},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_button_created_per_route(hass: HomeAssistant) -> None:
    routes = [
        {"name": "lundi_matin", "weekday": "monday", "time": "07:30",
         "waypoints": [{"label": "École", "place_id": "ChIJXXX"}]},
        {"name": "lundi_soir", "weekday": "monday", "time": "16:00",
         "waypoints": [{"label": "Maison", "place_id": "ChIJYYY"}]},
    ]
    entry = await _setup_entry(hass, routes)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 2
    names = {e.original_name for e in entities}
    assert "lundi_matin" in names
    assert "lundi_soir" in names


async def test_button_press_logs(hass: HomeAssistant, caplog) -> None:
    routes = [
        {"name": "lundi_matin", "weekday": "monday", "time": "07:30",
         "waypoints": [{"label": "École", "place_id": "ChIJXXX"}]},
    ]
    await _setup_entry(hass, routes)
    await hass.services.async_call(
        "button", "press",
        {"entity_id": "button.lundi_matin"},
        blocking=True,
    )
    assert "lundi_matin" in caplog.text


async def test_no_routes_no_buttons(hass: HomeAssistant) -> None:
    entry = await _setup_entry(hass, routes=[])
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert entities == []


async def test_buttons_reload_after_options_change(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"client_id": "cid", "client_secret": "csec",
              "refresh_token": "rtok", "proxy_url": "https://localhost:4443"},
        options={CONF_ROUTES: [
            {"name": "lundi_matin", "weekday": "monday", "time": "07:30",
             "waypoints": [{"label": "École", "place_id": "ChIJXXX"}]},
        ]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 1

    hass.config_entries.async_update_entry(
        entry,
        options={CONF_ROUTES: [
            {"name": "lundi_matin", "weekday": "monday", "time": "07:30",
             "waypoints": [{"label": "École", "place_id": "ChIJXXX"}]},
            {"name": "lundi_soir", "weekday": "monday", "time": "16:00",
             "waypoints": [{"label": "Maison", "place_id": "ChIJYYY"}]},
        ]},
    )
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 2
