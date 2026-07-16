"""Diagnostics support for the OASE integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN_DATA
from .coordinator import OaseConfigEntry

# Redacted anywhere these keys appear in the (nested) diagnostics payload:
# credentials/tokens plus anything that identifies the account's hardware.
TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_TOKEN_DATA,
    "refresh_token",
    "serial_number",
    "unique_id",
    "id",
    # Account holder PII from the inventory ``user`` object.
    "given_name",
    "surname",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OaseConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    inventory = coordinator.data

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
            },
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "inventory": async_redact_data(
                asdict(inventory) if inventory is not None else {}, TO_REDACT
            ),
        },
    }
