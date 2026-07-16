"""Tests for the OASE socket switches."""

from __future__ import annotations

from unittest.mock import MagicMock

from pyoase import onet

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.oase.const import DOMAIN

from .conftest import GATEWAY_ID


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_switches_created_with_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Three socket switches are created and reflect the inventory state."""
    await _setup(hass, mock_config_entry)
    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{GATEWAY_ID}_socket1"
    )
    assert entity_id is not None
    # socket1 is ``true`` in the fixture.
    assert hass.states.get(entity_id).state == STATE_ON

    for index in (1, 2, 3):
        assert (
            entity_registry.async_get_entity_id(
                Platform.SWITCH, DOMAIN, f"{GATEWAY_ID}_socket{index}"
            )
            is not None
        )


async def test_turn_off_calls_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Turning a socket off relays the matching O-Net command via the client."""
    await _setup(hass, mock_config_entry)
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{GATEWAY_ID}_socket1"
    )

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.return_value.async_set_socket.assert_awaited_once_with(
        GATEWAY_ID, onet.Socket.SOCKET_1, False
    )


async def test_turn_on_calls_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Turning a socket on relays the matching O-Net command via the client."""
    await _setup(hass, mock_config_entry)
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        Platform.SWITCH, DOMAIN, f"{GATEWAY_ID}_socket2"
    )

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.return_value.async_set_socket.assert_awaited_once_with(
        GATEWAY_ID, onet.Socket.SOCKET_2, True
    )
