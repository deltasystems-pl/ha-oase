"""Light platform for the OASE FM-Master dimmable outlet."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyoase import OaseError, OaseGatewayOfflineError, onet

from .const import DOMAIN
from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity, OaseGatewayEntity

# HA effect name <-> OASE effect id.
_EFFECT_BY_NAME = {name: eid for eid, name in onet.LED_EFFECT_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the dimmable outlet and any RGB LED channels."""
    coordinator = entry.runtime_data.coordinator
    entities: list[LightEntity] = []
    for gateway in coordinator.data.gateways:
        if gateway.sockets is not None:
            entities.append(OaseDimmerLight(coordinator, gateway.id))
        for device in gateway.devices:
            if device.id is None or device.device_number is None or not device.is_led:
                continue
            entities.extend(
                OaseRgbChannelLight(coordinator, gateway.id, device.id, channel)
                for channel in range(1, len(device.led_channels) + 1)
            )
    async_add_entities(entities)


class OaseDimmerLight(OaseGatewayEntity, LightEntity):
    """The dimmable outlet of an FM-Master (dimmer on/off + 0-255 level)."""

    _attr_translation_key = "dimmer"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: OaseDataUpdateCoordinator, gateway_id: str) -> None:
        """Initialise the dimmer light."""
        super().__init__(coordinator, gateway_id)
        self._attr_unique_id = f"{gateway_id}_dimmer"

    @property
    def is_on(self) -> bool | None:
        """Return whether the dimmable outlet is on."""
        gateway = self.gateway
        if gateway is None or gateway.sockets is None:
            return None
        return gateway.sockets.dimmer_on

    @property
    def brightness(self) -> int | None:
        """Return the current brightness (0-255), mapping 1:1 to the dimmer value."""
        gateway = self.gateway
        if gateway is None or gateway.sockets is None:
            return None
        return gateway.sockets.dimmer_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the outlet on, optionally setting a brightness level."""
        client = self.coordinator.client
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        try:
            if brightness is not None:
                await client.async_set_dimmer_value(self._gateway_id, brightness)
            else:
                await client.async_set_socket(self._gateway_id, onet.Socket.DIMMER_ONOFF, True)
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        # Setting a level does not itself flip the on/off channel, so only the
        # value is assumed here; the poll reports the real dimmer_on state.
        if brightness is not None:
            self.coordinator.apply_socket_update(self._gateway_id, dimmer_value=brightness)
        else:
            self.coordinator.apply_socket_update(self._gateway_id, dimmer_on=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmable outlet off."""
        try:
            await self.coordinator.client.async_set_socket(
                self._gateway_id, onet.Socket.DIMMER_ONOFF, False
            )
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_socket_update(self._gateway_id, dimmer_on=False)
        await self.coordinator.async_request_refresh()


class OaseRgbChannelLight(OaseDeviceEntity, LightEntity):
    """One RGB channel of an OASE LED controller (colour + brightness + effect).

    State is read over RDM; changes are written as a SET_LIVE_SCENE scene-5 packet
    (the same path the OASE app uses). A command is a read-modify-write of the
    channel's 9-byte record so unspecified fields (effect, speed) are preserved.
    """

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = list(onet.LED_EFFECT_NAMES.values())

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
        channel: int,
    ) -> None:
        """Initialise one RGB channel light."""
        super().__init__(coordinator, gateway_id, device_id)
        self._channel = channel
        self._attr_translation_key = "rgb_channel"
        self._attr_translation_placeholders = {"channel": str(channel)}
        self._attr_unique_id = f"{device_id}_rgb{channel}"

    @property
    def _record(self) -> onet.LedRecord | None:
        device = self.device
        if device is None or not 1 <= self._channel <= len(device.led_channels):
            return None
        return device.led_channels[self._channel - 1]

    @property
    def available(self) -> bool:
        """Available only while the channel's live state is known."""
        return super().available and self._record is not None

    @property
    def is_on(self) -> bool | None:
        record = self._record
        return record.on if record is not None else None

    @property
    def brightness(self) -> int | None:
        record = self._record
        return record.brightness if record is not None else None

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        record = self._record
        if record is None:
            return None
        return (record.red, record.green, record.blue)

    @property
    def effect(self) -> str | None:
        record = self._record
        if record is None:
            return None
        return onet.LED_EFFECT_NAMES.get(record.effect)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Apply colour/brightness/effect and switch the channel on."""
        record = self._record
        if record is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        changes: dict[str, Any] = {"on": True}
        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            changes.update(red=r, green=g, blue=b)
        if ATTR_BRIGHTNESS in kwargs:
            changes["brightness"] = kwargs[ATTR_BRIGHTNESS]
        if ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] in _EFFECT_BY_NAME:
            changes["effect"] = _EFFECT_BY_NAME[kwargs[ATTR_EFFECT]]
        await self._async_write(replace(record, **changes))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the channel off, preserving its colour/effect."""
        record = self._record
        if record is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        await self._async_write(replace(record, on=False))

    async def _async_write(self, record: onet.LedRecord) -> None:
        try:
            await self.coordinator.client.async_set_led_channel(
                self._gateway_id, self._channel, record
            )
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_led_update(self._device_id, self._channel, record)
        await self.coordinator.async_request_refresh()
