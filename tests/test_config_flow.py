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
    assert "edit_schedule" in result["menu_options"]
    assert "edit_waypoints" in result["menu_options"]


async def test_reconfigure_edit_schedule_keeps_waypoints(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop A", "place_id": "ChIJAAA", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _init_reconfigure_flow(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "edit_schedule"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "edit_schedule"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"name": "lundi_soir", "weekday": ["friday"], "time": "18:00"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert subentry.data["name"] == "lundi_soir"
    assert subentry.data["weekday"] == ["friday"]
    assert subentry.data["time"] == "18:00"
    assert subentry.data["waypoints"] == [{"label": "Stop A", "place_id": "ChIJAAA"}]


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
    assert "waypoint_index" in result["data_schema"].schema


async def test_manage_waypoints_add_new(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    # No waypoints — waypoint_index field should not be present
    assert "waypoint_index" not in result["data_schema"].schema

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
    assert len(subentry.data["waypoints"]) == 2

    result = await _enter_manage_waypoints(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "delete_selected", "waypoint_index": "0"}
    )
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
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "edit_selected", "waypoint_index": "0"}
    )
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


async def test_manage_waypoints_error_no_selection(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    result, flow_id = await _init_route_flow(hass, entry)
    await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "Stop A", "place_id": "ChIJAAA", "action": "done"}
    )
    await hass.async_block_till_done()
    subentry = next(iter(entry.subentries.values()))

    result = await _enter_manage_waypoints(hass, entry, subentry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"waypoint_action": "delete_selected"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "waypoint_not_selected"}
