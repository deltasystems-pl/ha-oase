"""Number platform for OASE EGC pump power."""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyoase import OaseError, OaseGatewayOfflineError, onet, rdm

from .const import DOMAIN
from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up pump power controls and RGB effect-speed controls."""
    coordinator = entry.runtime_data.coordinator
    entities: list[NumberEntity] = []
    for gateway in coordinator.data.gateways:
        for device in gateway.devices:
            if device.id is None or device.device_number is None:
                continue
            if device.can_set_power:
                entities.append(OasePumpPowerNumber(coordinator, gateway.id, device.id))
            if device.is_led:
                entities.extend(
                    OaseRgbSpeedNumber(coordinator, gateway.id, device.id, channel)
                    for channel in range(1, len(device.led_channels) + 1)
                )
    async_add_entities(entities)


class OasePumpPowerNumber(OaseDeviceEntity, NumberEntity):
    """An EGC pump's power level, as the percentage the OASE app shows.

    The wire value is a raw 0-255 byte; the app displays it rounded **up**
    (``ceil(raw*100/255)``), so 0x7F reads as 50% and 0x80 as 51%. We mirror that
    exactly so HA and the app never disagree by a percent.
    """

    _attr_translation_key = "pump_power"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the pump power control."""
        super().__init__(coordinator, gateway_id, device_id)
        self._attr_unique_id = f"{device_id}_pump_power"

    @property
    def native_value(self) -> float | None:
        """Return the current power level as a percentage."""
        device = self.device
        if device is None or device.pump_state is None:
            return None
        return rdm.raw_to_percent(device.pump_state.dimmer_value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the pump's power level."""
        device = self.device
        if device is None or device.device_number is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        raw = rdm.percent_to_raw(value)
        try:
            await self.coordinator.client.async_set_pump_power(
                self._gateway_id, device.device_number, raw
            )
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_pump_update(self._device_id, dimmer_value=raw)
        await self.coordinator.async_request_refresh()


class OaseRgbSpeedNumber(OaseDeviceEntity, NumberEntity):
    """Effect speed (0-100%) of one RGB channel.

    Only meaningful while the channel is running an effect. It is a tuning
    parameter, so it lives in the Configuration category. A change is a
    read-modify-write of the channel's record, preserving colour/effect.
    """

    _attr_translation_key = "rgb_speed"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
        channel: int,
    ) -> None:
        """Initialise one RGB effect-speed control."""
        super().__init__(coordinator, gateway_id, device_id)
        self._channel = channel
        self._attr_translation_placeholders = {"channel": str(channel)}
        self._attr_unique_id = f"{device_id}_rgb{channel}_speed"

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
    def native_value(self) -> float | None:
        record = self._record
        return onet.led_period_to_speed(record.period) if record is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the effect speed, preserving colour and effect."""
        record = self._record
        if record is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        updated = replace(record, period=onet.led_speed_to_period(value))
        try:
            await self.coordinator.client.async_set_led_channel(
                self._gateway_id, self._channel, updated
            )
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_led_update(self._device_id, self._channel, updated)
        await self.coordinator.async_request_refresh()
