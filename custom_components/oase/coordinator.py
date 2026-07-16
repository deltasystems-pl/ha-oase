"""DataUpdateCoordinator for the OASE integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyoase import (
    Device,
    Gateway,
    Inventory,
    OaseAuth,
    OaseAuthError,
    OaseCloudClient,
    OaseConnectionError,
    OaseError,
    OaseGatewayOfflineError,
)

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN_DATA, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OaseConfigEntry = ConfigEntry[OaseRuntimeData]


@dataclass
class OaseRuntimeData:
    """Data kept on a config entry while it is loaded."""

    client: OaseCloudClient
    coordinator: OaseDataUpdateCoordinator


class OaseDataUpdateCoordinator(DataUpdateCoordinator[Inventory]):
    """Poll the OASE cloud for the account inventory and device state."""

    config_entry: OaseConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OaseConfigEntry,
        client: OaseCloudClient,
        auth: OaseAuth,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self._auth = auth
        # Snapshot the credentials so the update listener can tell a genuine
        # reconfiguration apart from a silent refresh-token rotation.
        self._email = config_entry.data.get(CONF_EMAIL)
        self._password = config_entry.data.get(CONF_PASSWORD)
        # Cache of static per-device info (software version) keyed by device number,
        # so we read it over RDM once rather than on every poll.
        self._software_versions: dict[int, str | None] = {}

    async def _async_update_data(self) -> Inventory:
        """Fetch the latest inventory, mapping library errors to HA errors."""
        try:
            inventory = await self.client.async_get_inventory()
        except OaseAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (OaseGatewayOfflineError, OaseConnectionError, OaseError) as err:
            raise UpdateFailed(str(err)) from err

        inventory = await self._async_refresh_egc_states(inventory)

        # A refresh may have rotated the refresh token; persist it if so.
        self._persist_token_data()
        return inventory

    async def _async_refresh_egc_states(self, inventory: Inventory) -> Inventory:
        """Overlay authoritative EGC-device state read live over RDM.

        The cloud caches (``dmxPumpState``, ``rdmData``) only advance on an app action
        or a device push — they do **not** reflect commands we send (verified: pump
        state stayed stale for 40 s+ after a write). So for each connected device we
        read the true state over RDM and patch it in. Any RDM hiccup falls back to the
        cached state rather than failing the whole update.
        """
        gateways = []
        for gateway in inventory.gateways:
            devices = list(gateway.devices)
            if gateway.is_online:
                for i, device in enumerate(devices):
                    devices[i] = await self._async_patch_device(gateway.id, device)
            gateways.append(replace(gateway, devices=devices))
        return replace(inventory, gateways=gateways)

    async def _async_patch_device(self, gateway_id: str, device: Device) -> Device:
        """Return ``device`` with pump/LED state + diagnostics from live RDM reads."""
        number = device.device_number
        if number is None or not device.is_connected:
            return device
        if device.pump_state is not None:
            try:
                on = await self.client.async_get_device_on(gateway_id, number)
                raw = await self.client.async_get_pump_power(gateway_id, number)
            except OaseError as err:
                _LOGGER.debug("RDM pump read failed for %s: %s", number, err)
            else:
                device = replace(
                    device, pump_state=replace(device.pump_state, device_on=on, dimmer_value=raw)
                )
        if device.is_led:
            try:
                channels = await self.client.async_get_led_channels(gateway_id, number)
            except OaseError as err:
                _LOGGER.debug("RDM LED read failed for %s: %s", number, err)
            else:
                device = replace(device, led_channels=tuple(channels))
        # Diagnostics: operating hours live, software version cached (it never changes).
        try:
            hours = await self.client.async_get_operating_hours(gateway_id, number)
        except OaseError as err:
            _LOGGER.debug("RDM hours read failed for %s: %s", number, err)
            hours = device.operating_hours
        if number not in self._software_versions:
            try:
                self._software_versions[number] = (
                    await self.client.async_get_software_version(gateway_id, number)
                )
            except OaseError as err:
                _LOGGER.debug("RDM sw-version read failed for %s: %s", number, err)
        return replace(
            device,
            operating_hours=hours,
            software_version=self._software_versions.get(number),
        )

    def _persist_token_data(self) -> None:
        """Store refreshed token data back onto the config entry when it changes."""
        token_data = self._auth.token_data
        if token_data == self.config_entry.data.get(CONF_TOKEN_DATA):
            return
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_TOKEN_DATA: token_data},
        )

    def credentials_changed(self, entry: OaseConfigEntry) -> bool:
        """Return True if the entry's credentials differ from the running client.

        Used by the update listener so that persisting a rotated refresh token
        (which only touches ``CONF_TOKEN_DATA``) does not trigger a reload.
        """
        return (
            entry.data.get(CONF_EMAIL) != self._email
            or entry.data.get(CONF_PASSWORD) != self._password
        )

    def apply_socket_update(self, gateway_id: str, **changes: Any) -> None:
        """Reflect a just-accepted socket command in the cached state immediately.

        Without this the UI can lag a command by up to ten seconds: HA debounces
        ``async_request_refresh`` with a cooldown, so a command issued inside that
        window has its refresh deferred. The device applies commands in ~0.2s and
        the cloud publishes them in ~0.5s, so showing the requested state at once
        is accurate; the next poll overwrites it with the authoritative value.

        Only called after the device has acknowledged the command.
        """
        if self.data is None:
            return
        gateway = self.data.gateway(gateway_id)
        if gateway is None or gateway.sockets is None:
            return
        updated = replace(gateway, sockets=replace(gateway.sockets, **changes))
        self.async_set_updated_data(
            replace(
                self.data,
                gateways=[g if g.id != gateway_id else updated for g in self.data.gateways],
            )
        )

    def apply_pump_update(self, device_id: str, **changes: Any) -> None:
        """Reflect a just-acknowledged EGC device command in the cached state.

        Same rationale as :meth:`apply_socket_update`: RDM commands are acknowledged
        by the device itself, but the cloud's ``dmxPumpState`` only catches up on the
        next poll (and HA debounces refreshes), so show the requested state at once.
        """
        if self.data is None:
            return
        gateways = []
        for gateway in self.data.gateways:
            devices = [
                replace(d, pump_state=replace(d.pump_state, **changes))
                if d.id == device_id and d.pump_state is not None
                else d
                for d in gateway.devices
            ]
            gateways.append(replace(gateway, devices=devices))
        self.async_set_updated_data(replace(self.data, gateways=gateways))

    def apply_pump_show(self, device_id: str, mode: int) -> None:
        """Reflect a just-sent pump-show command immediately."""
        self.apply_pump_update(
            device_id,
            fc_mode=mode,
            fc_status="DfcOn" if mode else "DfcOff",
        )

    def apply_led_update(self, device_id: str, channel: int, record) -> None:
        """Reflect a just-sent LED channel write in the cached state immediately."""
        if self.data is None:
            return
        gateways = []
        for gateway in self.data.gateways:
            devices = []
            for d in gateway.devices:
                if d.id == device_id and 1 <= channel <= len(d.led_channels):
                    chans = list(d.led_channels)
                    chans[channel - 1] = record
                    d = replace(d, led_channels=tuple(chans))
                devices.append(d)
            gateways.append(replace(gateway, devices=devices))
        self.async_set_updated_data(replace(self.data, gateways=gateways))

    def get_gateway(self, gateway_id: str) -> Gateway | None:
        """Return the gateway with ``gateway_id`` from the latest inventory."""
        if self.data is None:
            return None
        return self.data.gateway(gateway_id)

    def get_device(self, device_id: str) -> Device | None:
        """Return the attached device with ``device_id`` from the latest inventory."""
        if self.data is None:
            return None
        for gateway in self.data.gateways:
            for device in gateway.devices:
                if device.id == device_id:
                    return device
        return None
