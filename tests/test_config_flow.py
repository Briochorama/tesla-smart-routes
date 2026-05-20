import pytest
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tesla_nav.config_flow import TeslaLocalOAuth2Implementation
from custom_components.tesla_nav.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PROXY_URL,
    DOMAIN,
)

MOCK_ENTRY_DATA = {
    CONF_CLIENT_ID: "test_cid",
    CONF_CLIENT_SECRET: "test_csec",
    CONF_PROXY_URL: "https://localhost:4443",
    "token": {
        "access_token": "mock_access",
        "refresh_token": "mock_refresh",
        "token_type": "Bearer",
        "expires_in": 7200,
        "expires_at": 9999999999,
    },
}

VIN_CHONK = "XP7YGCES6RB264282"


async def _create_main_entry(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    return entry


async def _init_route_flow(hass: HomeAssistant, entry):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "route"),
        context={"source": config_entries.SOURCE_USER},
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"name": "lundi_matin"},
    )
    assert result["step_id"] == "vin_source"
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"vin_source": "manual"},
    )
    assert result["step_id"] == "vin_manual"
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"vin": VIN_CHONK},
    )
    return result, flow_id


# ── Main config flow ────────────────────────────────────────────────────────

async def test_config_flow_shows_form(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "client_id" in result["data_schema"].schema
    assert "client_secret" in result["data_schema"].schema
    assert "proxy_url" in result["data_schema"].schema
    assert "refresh_token" not in result["data_schema"].schema


async def test_config_flow_initiates_oauth(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch.object(
        TeslaLocalOAuth2Implementation,
        "async_generate_authorize_url",
        return_value="https://auth.tesla.com/authorize?mock=1",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_CLIENT_ID: "cid", CONF_CLIENT_SECRET: "csec", CONF_PROXY_URL: "https://localhost:4443"},
        )
    assert result["type"] == FlowResultType.EXTERNAL_STEP
    assert "auth.tesla.com" in result["url"]


async def test_config_flow_only_one_entry(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


# ── Subentry flow ────────────────────────────────────────────────────────────

async def test_subentry_creates_route_no_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "add_another"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "lundi_matin"

    subentry = next(iter(entry.subentries.values()))
    assert subentry.data["waypoints"] == []
    assert subentry.data["vin"] == VIN_CHONK
    assert subentry.data["vin_source"] == "manual"


async def test_subentry_creates_route_with_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "École", "place_id": "ChIJXXX", "action": "add_another"}
    )
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


async def _init_reconfigure_flow(hass: HomeAssistant, entry, subentry):
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, "route"),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subentry.subentry_id},
    )


async def test_reconfigure_shows_menu(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _init_reconfigure_flow(hass, entry, subentry)
    assert result["type"] == FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    assert "edit_route" in result["menu_options"]
    assert "edit_vehicle" in result["menu_options"]
    assert "edit_waypoints" in result["menu_options"]


@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_reconfigure_edit_route_keeps_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop A", "place_id": "ChIJAAA", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _init_reconfigure_flow(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "edit_route"}
    )
    assert result["step_id"] == "edit_route"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "lundi_soir"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert subentry.data["name"] == "lundi_soir"
    assert subentry.data["vin"] == VIN_CHONK
    assert subentry.data["waypoints"] == [{"label": "Stop A", "place_id": "ChIJAAA"}]


async def test_reconfigure_edit_vehicle_manual(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _init_reconfigure_flow(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "edit_vehicle"}
    )
    assert result["step_id"] == "vin_source"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"vin_source": "manual"}
    )
    assert result["step_id"] == "vin_manual"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"vin": "LRW3E7FSXPC660715"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert subentry.data["vin"] == "LRW3E7FSXPC660715"
    assert subentry.data["vin_source"] == "manual"
    assert subentry.data["waypoints"] == []


async def _enter_manage_waypoints(hass, entry, subentry):
    result = await _init_reconfigure_flow(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "edit_waypoints"}
    )
    assert result["step_id"] == "manage_waypoints"
    return result


async def test_manage_waypoints_shows_existing(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop A", "place_id": "ChIJAAA", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manage_waypoints"
    assert "waypoint_index" not in result["data_schema"].schema


async def test_manage_waypoints_add_new(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "add_new"}
    )
    assert result["step_id"] == "add_single_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"label": "Stop A", "place_id": "ChIJAAA"}
    )
    assert result["step_id"] == "manage_waypoints"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "done"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data["waypoints"] == [{"label": "Stop A", "place_id": "ChIJAAA"}]


async def _select_waypoint_and_action(hass, flow_id, index, action):
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"waypoint_action": "edit_or_delete"}
    )
    assert result["step_id"] == "select_waypoint"
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"waypoint_index": str(index)}
    )
    assert result["step_id"] == "manage_waypoint_action"
    return await hass.config_entries.subentries.async_configure(
        flow_id, {"waypoint_edit_action": action}
    )


async def test_manage_waypoints_delete(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop A", "place_id": "ChIJAAA", "action": "add_another"}
    )
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop B", "place_id": "ChIJBBB", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    result = await _select_waypoint_and_action(hass, result["flow_id"], 0, "delete")
    assert result["step_id"] == "manage_waypoints"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "done"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert len(subentry.data["waypoints"]) == 1
    assert subentry.data["waypoints"][0] == {"label": "Stop B", "place_id": "ChIJBBB"}


async def test_manage_waypoints_edit(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Old label", "place_id": "ChIJOLD", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    result = await _select_waypoint_and_action(hass, result["flow_id"], 0, "edit")
    assert result["step_id"] == "edit_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"label": "New label", "place_id": "ChIJNEW"}
    )
    assert result["step_id"] == "manage_waypoints"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "done"}
    )
    assert result["reason"] == "reconfigure_successful"
    assert subentry.data["waypoints"] == [{"label": "New label", "place_id": "ChIJNEW"}]
