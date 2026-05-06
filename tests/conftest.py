"""Global test fixtures."""
import pathlib
import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def hass_config_dir():
    """Point HA to the project root so it finds custom_components/tesla_nav."""
    return str(pathlib.Path(__file__).parent.parent)


@pytest.fixture(autouse=True)
async def clear_custom_components_cache(hass):
    """Clear the custom components loader cache after HA starts.

    The cache is populated during startup before our path is fully established,
    resulting in an empty cache. Clearing it forces a fresh scan.
    """
    from homeassistant.loader import DATA_CUSTOM_COMPONENTS
    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
