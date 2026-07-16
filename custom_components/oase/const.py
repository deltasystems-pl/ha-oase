"""Constants for the OASE integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "oase"

#: Platforms this integration forwards config entries to.
PLATFORMS: Final[list[Platform]] = [
    Platform.SWITCH,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

#: How often to poll the OASE cloud for fresh inventory/state (seconds).
DEFAULT_SCAN_INTERVAL: Final = 30

MANUFACTURER: Final = "OASE"

#: Fallback name for a gateway device when the account provides no custom name.
DEFAULT_GATEWAY_NAME: Final = "FM-Master"

# --- Config entry keys ----------------------------------------------------------
# ``email``/``password`` match homeassistant.const, but are declared here so the
# whole config-entry contract lives in one place. ``token_data`` is OASE-specific:
# it holds the persisted refresh token (see OaseAuth.token_data).
CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_TOKEN_DATA: Final = "token_data"
