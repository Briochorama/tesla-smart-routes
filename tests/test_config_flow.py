import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tesla_nav.const import CONF_ROUTES, DOMAIN


async def test_config_flow_shows_form(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "client_id" in result["data_schema"].schema
    assert "proxy_url" in result["data_schema"].schema


async def test_config_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "refresh_token": "test_refresh",
            "proxy_url": "https://localhost:4443",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tesla Nav"
    assert result["data"]["client_id"] == "test_client_id"
    assert result["data"]["proxy_url"] == "https://localhost:4443"


async def test_config_flow_only_one_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "client_id": "cid",
            "client_secret": "csec",
            "refresh_token": "rtok",
            "proxy_url": "https://localhost:4443",
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def _create_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"client_id": "cid", "client_secret": "csec",
         "refresh_token": "rtok", "proxy_url": "https://localhost:4443"},
    )
    return hass.config_entries.async_entries(DOMAIN)[0]


async def test_options_add_route(hass: HomeAssistant) -> None:
    entry = await _create_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_route"}
    )
    assert result["step_id"] == "add_route"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "lundi_matin",
            "weekday": "monday",
            "time": "07:30",
            "waypoints": "École | ChIJPceHK8L1ikcRs_TCr4OFP3I\nTravail | ChIJjxxNp05fikcR3DlfSF8bxso",
        },
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    routes = result["data"][CONF_ROUTES]
    assert len(routes) == 1
    assert routes[0]["name"] == "lundi_matin"
    assert routes[0]["weekday"] == "monday"
    assert routes[0]["waypoints"][0] == {"label": "École", "place_id": "ChIJPceHK8L1ikcRs_TCr4OFP3I"}
    assert routes[0]["waypoints"][1] == {"label": "Travail", "place_id": "ChIJjxxNp05fikcR3DlfSF8bxso"}


async def test_options_remove_route(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"client_id": "cid", "client_secret": "csec",
              "refresh_token": "rtok", "proxy_url": "https://localhost:4443"},
        options={CONF_ROUTES: [
            {"name": "lundi_matin", "weekday": "monday", "time": "07:30", "waypoints": []},
            {"name": "lundi_soir", "weekday": "monday", "time": "16:00", "waypoints": []},
        ]},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_route"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"routes": ["lundi_matin"]}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "finish"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    routes = result["data"][CONF_ROUTES]
    assert len(routes) == 1
    assert routes[0]["name"] == "lundi_soir"


async def test_options_invalid_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "add_route"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "test", "weekday": "monday", "time": "07:30", "waypoints": "no pipe separator here"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"waypoints": "invalid_waypoints"}
