"""Tests for which entities each kind of EGC pump is given.

Issue #1: a filter pump such as an AquaMax answers the RDM control parameters
but has no flow-control shows and no cloud ``dmxPumpState``. It must get the
controls it can use, and none of the ones it cannot.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pyoase import Inventory

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oase.const import DOMAIN

from .conftest import DEVICE_ID, load_raw_inventory

# (platform, unique-id suffix) of every entity an EGC pump can be given.
PUMP_ENTITIES = {
    "switch": (Platform.SWITCH, "device_on"),
    "power": (Platform.NUMBER, "pump_power"),
    "show": (Platform.SELECT, "pump_show"),
    "status": (Platform.SENSOR, "fc_status"),
    "level": (Platform.SENSOR, "dimmer_value"),
    "hours": (Platform.SENSOR, "operating_hours"),
}


def _inventory(*, pump_state: bool) -> Inventory:
    """The fixture's pump, with or without the cloud's flow-control block."""
    raw = load_raw_inventory()
    if not pump_state:
        raw["gateways"][0]["devices"][0]["dmxPumpState"] = None
    return Inventory.from_dict(raw)


async def _entities(
    hass: HomeAssistant, entry: MockConfigEntry, client: MagicMock, *, pump_state: bool
) -> set[str]:
    """Set the integration up and name the pump entities that were created."""
    client.async_get_inventory = AsyncMock(return_value=_inventory(pump_state=pump_state))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    return {
        name
        for name, (platform, suffix) in PUMP_ENTITIES.items()
        if registry.async_get_entity_id(platform, DOMAIN, f"{DEVICE_ID}_{suffix}") is not None
    }


async def test_pump_without_cloud_state_gets_the_controls_it_supports(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """The AquaMax case: controls appear, shows do not."""
    created = await _entities(
        hass, mock_config_entry, mock_client.return_value, pump_state=False
    )
    assert created == {"switch", "power", "level", "hours"}


async def test_flow_control_pump_keeps_its_show_selector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A fountain pump is unaffected and still gets the full set."""
    created = await _entities(
        hass, mock_config_entry, mock_client.return_value, pump_state=True
    )
    assert created == set(PUMP_ENTITIES)
