from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.tesla_nav.const import DOMAIN

CREDENTIALS = {
    "client_id": "cid",
    "client_secret": "csec",
    "refresh_token": "rtok",
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


async def _add_route(
    hass: HomeAssistant,
    entry,
    name: str,
    weekday: list | None = None,
    time: str = "07:30",
    waypoints: list | None = None,
):
    if weekday is None:
        weekday = ["monday"]
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "route"),
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": name, "weekday": weekday, "time": time},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_waypoint"

    for wp in waypoints or []:
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"label": wp["label"], "place_id": wp["place_id"], "action": "add_another"}
        )
        assert result["step_id"] == "add_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"label": "", "place_id": "", "action": "done"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


async def test_no_routes_no_buttons(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert entities == []


async def test_button_appears_after_subentry_added(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    registry = er.async_get(hass)
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 0

    await _add_route(hass, entry, "lundi_matin")

    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 1
    assert entities[0].original_name == "lundi_matin"


async def test_button_created_per_route(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    await _add_route(hass, entry, "lundi_matin")
    await _add_route(hass, entry, "lundi_soir", time="16:00")

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 2
    names = {e.original_name for e in entities}
    assert "lundi_matin" in names
    assert "lundi_soir" in names


async def test_button_press_logs(hass: HomeAssistant, caplog) -> None:
    entry = await _create_main_entry(hass)
    await _add_route(hass, entry, "lundi_matin")

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    entity_id = entities[0].entity_id

    await hass.services.async_call(
        "button", "press",
        {"entity_id": entity_id},
        blocking=True,
    )
    assert "lundi_matin" in caplog.text
