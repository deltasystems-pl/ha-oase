"""The OASE integration.

Cloud-polling hub integration for OASE InScenio FM-Master (EGC / "OASE Control")
smart power controllers, backed by the :mod:`pyoase` library.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pyoase import OaseAuth, OaseCloudClient

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN_DATA, PLATFORMS
from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator, OaseRuntimeData


async def async_setup_entry(hass: HomeAssistant, entry: OaseConfigEntry) -> bool:
    """Set up OASE from a config entry."""
    session = async_get_clientsession(hass)
    auth = OaseAuth(
        session,
        entry.data.get(CONF_EMAIL),
        entry.data.get(CONF_PASSWORD),
        token_data=entry.data.get(CONF_TOKEN_DATA),
    )
    client = OaseCloudClient(session, auth)

    coordinator = OaseDataUpdateCoordinator(hass, entry, client, auth)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OaseRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OaseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: OaseConfigEntry) -> None:
    """Reload the entry when the user changes its credentials.

    Refresh-token rotation persists silently to the entry without a reload; only
    a genuine credential change (reauth/reconfigure) rebuilds the runtime.
    """
    if entry.runtime_data.coordinator.credentials_changed(entry):
        await hass.config_entries.async_reload(entry.entry_id)
