"""Sensor platform for OASE diagnostic and pump telemetry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from pyoase import PumpState

from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity, OaseGatewayEntity

# EgcFlowControlState values reported in ``fcStatus`` (see REVERSE_ENGINEERING.md),
# mapped to HA enum-slug options (translation keys must be lowercase slugs).
_FC_STATUS_SLUGS = {
    "SfcOff": "sfc_off",
    "DfcOff": "dfc_off",
    "SfcOn": "sfc_on",
    "DfcOn": "dfc_on",
    "ErrorCode": "error",
}
_FC_STATUS_OPTIONS = list(_FC_STATUS_SLUGS.values())


def _fc_status_slug(state: PumpState) -> StateType:
    """Map the raw ``fcStatus`` value to its enum slug."""
    return _FC_STATUS_SLUGS.get(state.fc_status) if state.fc_status else None


@dataclass(frozen=True, kw_only=True)
class OasePumpSensorEntityDescription(SensorEntityDescription):
    """Describes an OASE pump telemetry sensor."""

    value_fn: Callable[[PumpState], StateType]


PUMP_SENSORS: tuple[OasePumpSensorEntityDescription, ...] = (
    OasePumpSensorEntityDescription(
        key="fc_status",
        translation_key="pump_status",
        device_class=SensorDeviceClass.ENUM,
        options=_FC_STATUS_OPTIONS,
        value_fn=_fc_status_slug,
    ),
    OasePumpSensorEntityDescription(
        key="dimmer_value",
        translation_key="pump_level",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda state: state.dimmer_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up gateway and pump sensors."""
    coordinator = entry.runtime_data.coordinator
    entities: list[SensorEntity] = []
    for gateway in coordinator.data.gateways:
        if gateway.sockets is not None:
            entities.append(OaseGatewayDimmerSensor(coordinator, gateway.id))
        for device in gateway.devices:
            if device.id is None:
                continue
            if device.pump_state is not None:
                entities.extend(
                    OasePumpSensor(coordinator, gateway.id, device.id, description)
                    for description in PUMP_SENSORS
                )
            # Operating-hours counter is available on any EGC device (pump or LED).
            if device.device_number is not None:
                entities.append(OaseOperatingHoursSensor(coordinator, gateway.id, device.id))
    async_add_entities(entities)


class OaseGatewayDimmerSensor(OaseGatewayEntity, SensorEntity):
    """Exposes the raw dimmable-outlet level (0-255) as a diagnostic sensor."""

    _attr_translation_key = "dimmer_value"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: OaseDataUpdateCoordinator, gateway_id: str) -> None:
        """Initialise the dimmer-value sensor."""
        super().__init__(coordinator, gateway_id)
        self._attr_unique_id = f"{gateway_id}_dimmer_value"

    @property
    def native_value(self) -> int | None:
        """Return the current dimmer level (0-255)."""
        gateway = self.gateway
        if gateway is None or gateway.sockets is None:
            return None
        return gateway.sockets.dimmer_value


class OasePumpSensor(OaseDeviceEntity, SensorEntity):
    """A telemetry value of an attached OASE pump."""

    entity_description: OasePumpSensorEntityDescription

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
        description: OasePumpSensorEntityDescription,
    ) -> None:
        """Initialise a pump telemetry sensor."""
        super().__init__(coordinator, gateway_id, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the described value from the current pump state."""
        device = self.device
        if device is None or device.pump_state is None:
            return None
        return self.entity_description.value_fn(device.pump_state)


class OaseOperatingHoursSensor(OaseDeviceEntity, SensorEntity):
    """An EGC device's operating-hours counter (the app's runtime figure)."""

    _attr_translation_key = "operating_hours"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the operating-hours sensor."""
        super().__init__(coordinator, gateway_id, device_id)
        self._attr_unique_id = f"{device_id}_operating_hours"

    @property
    def native_value(self) -> int | None:
        """Return the operating hours reported over RDM."""
        device = self.device
        return device.operating_hours if device is not None else None
