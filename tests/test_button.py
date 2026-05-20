from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tesla_smart_routes.const import DOMAIN, CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_PROXY_URL

MOCK_ENTRY_DATA = {
    CONF_CLIENT_ID: "test_cid",
    CONF_CLIENT_SECRET: "test_csec",
    CONF_PROXY_URL: "https://localhost:4443",
    "token": {
        "access_token": "mock_access_token",
        "refresh_token": "mock_refresh_token",
        "token_type": "Bearer",
        "expires_in": 7200,
        "expires_at": 9999999999,
    },
}


async def _create_main_entry(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _add_route(
    hass: HomeAssistant,
    entry,
    name: str,
    waypoints: list | None = None,
):
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "route"),
        context={"source": config_entries.SOURCE_USER},
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"name": name},
    )
    assert result["step_id"] == "vin_source"
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"vin_source": "manual"},
    )
    assert result["step_id"] == "vin_manual"
    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"vin": "XP7YGCES6RB264282"},
    )
    assert result["step_id"] == "add_waypoint"

    for wp in waypoints or []:
        result = await hass.config_entries.subentries.async_configure(
            flow_id, {"label": wp["label"], "place_id": wp["place_id"], "action": "add_another"}
        )
        assert result["step_id"] == "add_waypoint"

    result = await hass.config_entries.subentries.async_configure(
        flow_id, {"label": "", "place_id": "", "action": "done"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
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
    await _add_route(hass, entry, "lundi_soir")

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 2
    names = {e.original_name for e in entities}
    assert "lundi_matin" in names
    assert "lundi_soir" in names


async def test_button_press_sends_route(hass: HomeAssistant) -> None:
    entry = await _create_main_entry(hass)
    await _add_route(
        hass, entry, "lundi_matin",
        waypoints=[{"label": "École", "place_id": "ChIJXXX"}],
    )

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    entity_id = entities[0].entity_id

    mock_post = AsyncMock()
    mock_post.status = 200
    mock_post.raise_for_status = MagicMock()
    mock_post.json = AsyncMock(return_value={"response": {"result": True, "reason": ""}})
    mock_post.__aenter__ = AsyncMock(return_value=mock_post)
    mock_post.__aexit__ = AsyncMock(return_value=False)

    mock_get = AsyncMock()
    mock_get.status = 200
    mock_get.json = AsyncMock(return_value={"response": {"state": "online"}})
    mock_get.__aenter__ = AsyncMock(return_value=mock_get)
    mock_get.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        return_value=None,
    ), patch(
        "aiohttp.ClientSession.post",
        return_value=mock_post,
    ), patch(
        "aiohttp.ClientSession.get",
        return_value=mock_get,
    ), patch(
        "asyncio.sleep",
        return_value=None,
    ):
        await hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )

    mock_post.raise_for_status.assert_called_once()
    mock_post.json.assert_called_once()
    mock_get.__aenter__.assert_called_once()  # vehicle state polled once before "online"
