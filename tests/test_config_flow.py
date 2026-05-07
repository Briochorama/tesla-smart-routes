from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tesla_nav.const import DOMAIN

CREDENTIALS = {
    "client_id": "test_client_id",
    "client_secret": "test_secret",
    "refresh_token": "test_refresh",
    "proxy_url": "https://localhost:4443",
}


async def _create_main_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return hass.config_entries.async_entries(DOMAIN)[0]


async def _init_route_flow(hass: HomeAssistant, entry):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "route"),
        context={"source": config_entries.SOURCE_USER},
    )
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "lundi_matin", "weekday": ["monday"], "time": "07:30"},
    ), result["flow_id"]


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
    result = await hass.config_entries.flow.async_configure(result["flow_id"], CREDENTIALS)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Tesla Nav"
    assert result["data"]["client_id"] == "test_client_id"
    assert result["data"]["proxy_url"] == "https://localhost:4443"


async def test_config_flow_only_one_entry(hass: HomeAssistant) -> None:
    await _create_main_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_subentry_creates_route_no_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_waypoint"

    # Empty submit → finish regardless of action
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "add_another"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "lundi_matin"

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["waypoints"] == []


async def test_subentry_creates_route_with_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "École", "place_id": "ChIJXXX", "action": "add_another"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Travail", "place_id": "ChIJYYY", "action": "done"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    subentry = next(iter(entry.subentries.values()))
    assert len(subentry.data["waypoints"]) == 2
    assert subentry.data["waypoints"][0] == {"label": "École", "place_id": "ChIJXXX"}
    assert subentry.data["waypoints"][1] == {"label": "Travail", "place_id": "ChIJYYY"}


async def test_subentry_waypoint_incomplete_error(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "École", "place_id": "", "action": "done"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "waypoint_incomplete"}
