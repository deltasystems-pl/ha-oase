"""Tests for the OASE diagnostics download."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pyoase import OaseError

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from .conftest import GATEWAY_ID


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _diagnostics(
    hass: HomeAssistant, hass_client: Any, entry: MockConfigEntry
) -> dict[str, Any]:
    await _setup(hass, entry)
    return await get_diagnostics_for_config_entry(hass, hass_client, entry)


async def test_raw_inventory_keeps_what_the_model_discards(
    hass: HomeAssistant,
    hass_client: Any,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """rdmData and dmxPumpState survive into the download.

    These are what a report about unsupported hardware turns on, and the
    parsed model reduces the first to a boolean and drops the rest.
    """
    diagnostics = await _diagnostics(hass, hass_client, mock_config_entry)

    device = diagnostics["raw_inventory"]["gateways"][0]["devices"][0]
    assert set(device["rdmData"]) == {"0x0050", "0x8039"}
    assert device["dmxPumpState"]["value"]["dimmerValue"] == 200
    assert device["deviceType"] == "GardenPump"


async def test_raw_inventory_is_redacted(
    hass: HomeAssistant,
    hass_client: Any,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """Identifiers are redacted and unredactable blobs are dropped entirely."""
    diagnostics = await _diagnostics(hass, hass_client, mock_config_entry)

    gateway = diagnostics["raw_inventory"]["gateways"][0]
    assert gateway["id"] != GATEWAY_ID
    assert gateway["serialNumber"] == "**REDACTED**"
    assert diagnostics["raw_inventory"]["user"]["givenName"] == "**REDACTED**"
    # incrementStates hides the serial number inside base64 payloads, where
    # redaction by key cannot reach it.
    assert "incrementStates" not in gateway


async def test_raw_inventory_failure_does_not_fail_the_download(
    hass: HomeAssistant,
    hass_client: Any,
    mock_config_entry: MockConfigEntry,
    mock_auth: MagicMock,
    mock_client: MagicMock,
) -> None:
    """A cloud error is reported in place, not raised past the download."""
    await _setup(hass, mock_config_entry)
    mock_client.return_value.async_get_inventory_raw.side_effect = OaseError("boom")

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["raw_inventory"] == {"error": "boom"}
    assert diagnostics["coordinator"]["last_update_success"] is True
