"""Switch platform for OASE FM-Master on/off sockets."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyoase import OaseError, OaseGatewayOfflineError, onet

from .const import DOMAIN
from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity, OaseGatewayEntity

# (socket index 1-3, translation key, O-Net socket channel)
_SOCKETS: tuple[tuple[int, str, onet.Socket], ...] = (
    (1, "socket_1", onet.Socket.SOCKET_1),
    (2, "socket_2", onet.Socket.SOCKET_2),
    (3, "socket_3", onet.Socket.SOCKET_3),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OASE socket switches for each gateway that exposes sockets."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SwitchEntity] = []
    for gateway in coordinator.data.gateways:
        if gateway.sockets is not None:
            entities.extend(
                OaseSocketSwitch(coordinator, gateway.id, index, translation_key, socket)
                for index, translation_key, socket in _SOCKETS
            )
        # An EGC device (pump) has its own on/off, independent of its outlet.
        entities.extend(
            OaseDeviceSwitch(coordinator, gateway.id, device.id)
            for device in gateway.devices
            if device.id is not None
            and device.device_number is not None
            and device.pump_state is not None
        )
    async_add_entities(entities)


class OaseSocketSwitch(OaseGatewayEntity, SwitchEntity):
    """A single switchable outlet (socket 1-3) on an FM-Master."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        index: int,
        translation_key: str,
        socket: onet.Socket,
    ) -> None:
        """Initialise the socket switch."""
        super().__init__(coordinator, gateway_id)
        self._index = index
        self._socket = socket
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{gateway_id}_socket{index}"

    @property
    def is_on(self) -> bool | None:
        """Return whether this socket is currently on."""
        gateway = self.gateway
        if gateway is None or gateway.sockets is None:
            return None
        return bool(getattr(gateway.sockets, f"socket{self._index}"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the socket on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the socket off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        try:
            await self.coordinator.client.async_set_socket(self._gateway_id, self._socket, on)
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_socket_update(self._gateway_id, **{f"socket{self._index}": on})
        await self.coordinator.async_request_refresh()


class OaseDeviceSwitch(OaseDeviceEntity, SwitchEntity):
    """The on/off state of an EGC device (e.g. an AquaMax pump).

    This is the device's own switch — the one the OASE app shows — driven over RDM,
    and is independent of the outlet supplying it: a pump switched off here stays off
    even when its socket has power.
    """

    _attr_translation_key = "device_on"

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the EGC device switch."""
        super().__init__(coordinator, gateway_id, device_id)
        self._attr_unique_id = f"{device_id}_device_on"

    @property
    def is_on(self) -> bool | None:
        """Return whether the device reports itself switched on."""
        device = self.device
        if device is None or device.pump_state is None:
            return None
        return device.pump_state.device_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the device on."""
        await self._async_set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the device off."""
        await self._async_set(False)

    async def _async_set(self, on: bool) -> None:
        device = self.device
        if device is None or device.device_number is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        try:
            await self.coordinator.client.async_set_device_on(
                self._gateway_id, device.device_number, on
            )
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_pump_update(self._device_id, device_on=on)
        await self.coordinator.async_request_refresh()
