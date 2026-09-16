"""Tests for the coordinator's read-only EGC capability probe.

Issue #1: the cloud publishes ``dmxPumpState`` only for pumps with Digital Flow
Control, so an AquaMax arrives looking like a device with nothing to control.
The coordinator therefore asks the device itself — by reading, never writing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant
from pyoase import Device, Inventory, OaseConnectionError, OaseResponseError, rdm

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import load_raw_inventory


def _inventory(device_type: str = "GardenPump", *, pump_state: bool = False) -> Inventory:
    """Build an inventory whose single device is of the given kind."""
    raw = load_raw_inventory()
    device = raw["gateways"][0]["devices"][0]
    device["deviceType"] = device_type
    if not pump_state:
        device["dmxPumpState"] = None
    return Inventory.from_dict(raw)


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> Device:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data.coordinator.data.gateways[0].devices[0]


async def _repoll(hass: HomeAssistant, entry: MockConfigEntry) -> Device:
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    return entry.runtime_data.coordinator.data.gateways[0].devices[0]


async def test_pump_without_cloud_state_is_discovered_by_reading_it(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A pump the cloud says nothing about still gets its controls."""
    mock_client.return_value.async_get_inventory = AsyncMock(return_value=_inventory())

    device = await _setup(hass, mock_config_entry)

    assert device.can_switch is True
    assert device.can_set_power is True
    assert device.pump_state is not None
    assert device.pump_state.device_on is True
    assert device.pump_state.dimmer_value == 128
    # Assembled from RDM, so it claims no shows it cannot run.
    assert device.pump_state.has_flow_control is False


async def test_a_rejected_read_is_not_asked_for_twice(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A device that rejects a control read is taken at its word."""
    client = mock_client.return_value
    client.async_get_inventory = AsyncMock(return_value=_inventory())
    client.async_get_device_on = AsyncMock(side_effect=OaseResponseError("nack"))
    client.async_get_pump_power = AsyncMock(side_effect=OaseResponseError("nack"))

    device = await _setup(hass, mock_config_entry)

    assert device.supported_pids == ()
    assert device.can_switch is False
    assert device.pump_state is None
    assert client.async_get_device_on.await_count == 1

    await _repoll(hass, mock_config_entry)
    assert client.async_get_device_on.await_count == 1


async def test_a_connection_failure_leaves_the_question_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A pump is never written off because the network was down."""
    client = mock_client.return_value
    client.async_get_inventory = AsyncMock(return_value=_inventory())
    client.async_get_device_on = AsyncMock(side_effect=OaseConnectionError("down"))
    client.async_get_pump_power = AsyncMock(side_effect=OaseConnectionError("down"))

    device = await _setup(hass, mock_config_entry)
    assert device.supported_pids == ()
    assert client.async_get_device_on.await_count == 1

    client.async_get_device_on = AsyncMock(return_value=True)
    client.async_get_pump_power = AsyncMock(return_value=64)

    device = await _repoll(hass, mock_config_entry)
    assert device.can_switch is True
    assert device.pump_state.dimmer_value == 64


async def test_led_controllers_are_not_probed_for_pump_controls(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """An RGB controller is not a pump; it must not gain pump entities."""
    client = mock_client.return_value
    client.async_get_inventory = AsyncMock(return_value=_inventory("GardenLed"))

    device = await _setup(hass, mock_config_entry)

    assert device.is_led is True
    assert device.supported_pids == ()
    assert device.pump_state is None
    assert client.async_get_device_on.await_count == 0
    assert client.async_get_pump_power.await_count == 0


async def test_cloud_pump_state_still_drives_the_reads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A pump the cloud does describe behaves exactly as before."""
    client = mock_client.return_value
    client.async_get_inventory = AsyncMock(return_value=_inventory(pump_state=True))

    device = await _setup(hass, mock_config_entry)

    assert device.supported_pids == (rdm.Pid.DEVICE_ON, rdm.Pid.PUMP_POWER)
    assert device.pump_state.has_flow_control is True
    assert device.pump_state.dimmer_value == 128  # the live read, not the cloud's 200
    assert client.async_get_device_on.await_count == 1


async def test_declared_parameters_are_read_once_and_kept(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """SUPPORTED_PARAMETERS reaches diagnostics without being re-read each poll."""
    client = mock_client.return_value
    client.async_get_inventory = AsyncMock(return_value=_inventory())

    device = await _setup(hass, mock_config_entry)
    assert device.declared_pids == (0x0050, 0x1010)
    assert client.async_get_supported_parameters.await_count == 1

    device = await _repoll(hass, mock_config_entry)
    assert device.declared_pids == (0x0050, 0x1010)
    assert client.async_get_supported_parameters.await_count == 1
