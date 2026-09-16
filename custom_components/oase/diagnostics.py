"""Diagnostics support for the OASE integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from pyoase import OaseError

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

# The same, for the raw cloud JSON — which is camelCase and so shares only part
# of its spelling with the parsed model.
TO_REDACT_RAW = {
    "id",
    "serialNumber",
    "macAddress",
    "macAddresses",
    "givenName",
    "surname",
    "photoUri",
}

# Dropped from the raw inventory before it is returned: a bulky base64 cache of
# O-Net request/reply pairs that carries the gateway's serial number inside its
# payloads, where redaction by key cannot reach it.
DROP_RAW = {"incrementStates"}


def _strip(value: Any) -> Any:
    """Recursively remove keys whose contents cannot be redacted."""
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in DROP_RAW}
    if isinstance(value, list):
        return [_strip(item) for item in value]
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OaseConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry.

    Includes the raw inventory JSON alongside the parsed model. The model keeps
    only what the integration uses — a device's ``rdmData``, for instance,
    survives it as a single boolean — and those discarded fields are the ones
    that say what unfamiliar hardware can do. Shipping both means one
    attachment on an issue is enough to answer why a device is missing its
    entities, instead of asking the reporter to run a script (see issue #1).
    """
    coordinator = entry.runtime_data.coordinator
    inventory = coordinator.data

    raw: Any
    try:
        raw = async_redact_data(
            _strip(await entry.runtime_data.client.async_get_inventory_raw()),
            TO_REDACT_RAW,
        )
    except OaseError as err:
        # Diagnostics are most valuable when something is wrong, so a failure
        # here reports itself rather than failing the whole download.
        raw = {"error": str(err)}

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
        "raw_inventory": raw,
    }
