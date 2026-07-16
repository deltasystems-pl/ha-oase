"""Binary sensor platform for OASE connectivity state."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity, OaseGatewayEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up connectivity binary sensors for gateways and attached devices."""
    coordinator = entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = []
    for gateway in coordinator.data.gateways:
        entities.append(OaseGatewayConnectivity(coordinator, gateway.id))
        for device in gateway.devices:
            if device.id is None:
                continue
            entities.append(OaseDeviceConnectivity(coordinator, gateway.id, device.id))
    async_add_entities(entities)


class OaseGatewayConnectivity(OaseGatewayEntity, BinarySensorEntity):
    """Reports whether the gateway is currently online with the cloud."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OaseDataUpdateCoordinator, gateway_id: str) -> None:
        """Initialise the gateway connectivity sensor."""
        super().__init__(coordinator, gateway_id)
        self._attr_unique_id = f"{gateway_id}_connectivity"

    @property
    def available(self) -> bool:
        """Stay available while offline so the online state is still reported."""
        return self.coordinator.last_update_success and self.gateway is not None

    @property
    def is_on(self) -> bool | None:
        """Return True when the gateway reports itself online."""
        gateway = self.gateway
        return gateway.is_online if gateway is not None else None


class OaseDeviceConnectivity(OaseDeviceEntity, BinarySensorEntity):
    """Reports whether an attached device is connected to its gateway."""

    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the attached-device connectivity sensor."""
        super().__init__(coordinator, gateway_id, device_id)
        self._attr_unique_id = f"{device_id}_connectivity"

    @property
    def available(self) -> bool:
        """Stay available while disconnected so the state is still reported."""
        return self.coordinator.last_update_success and self.device is not None

    @property
    def is_on(self) -> bool | None:
        """Return True when the attached device is connected."""
        device = self.device
        return device.is_connected if device is not None else None
