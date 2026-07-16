"""Base entities for the OASE integration."""

from __future__ import annotations

import json

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyoase import Device, Gateway

from .const import DEFAULT_GATEWAY_NAME, DOMAIN, MANUFACTURER
from .coordinator import OaseDataUpdateCoordinator

# Keys the OASE app has been seen to use for a user-assigned name inside the
# opaque ``customAttributesJson`` blob. Parsed best-effort only.
_NAME_KEYS = ("name", "Name", "displayName", "deviceName")


def name_from_custom_attributes(custom_attributes: str | None) -> str | None:
    """Best-effort extract a friendly name from a customAttributesJson blob."""
    if not custom_attributes:
        return None
    try:
        data = json.loads(custom_attributes)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    for key in _NAME_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


class OaseGatewayEntity(CoordinatorEntity[OaseDataUpdateCoordinator]):
    """Base class for entities that belong to the gateway itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OaseDataUpdateCoordinator, gateway_id: str) -> None:
        """Initialise the gateway entity and its device registry entry."""
        super().__init__(coordinator)
        self._gateway_id = gateway_id
        gateway = coordinator.get_gateway(gateway_id)
        info = gateway.info if gateway else None
        name = (
            name_from_custom_attributes(gateway.custom_attributes if gateway else None)
            or (info.name if info else None)
            or DEFAULT_GATEWAY_NAME
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway_id)},
            connections={
                (CONNECTION_NETWORK_MAC, mac) for mac in (info.mac_addresses if info else ())
            },
            manufacturer=MANUFACTURER,
            name=name,
            # The device's own long name ("FM-Master EGC Cloud") reads better than
            # the cloud's enum ("FmMasterWLanEgcCloudEsp"); fall back to the enum.
            model=(info.long_name if info else None)
            or (gateway.gateway_type if gateway else None),
            serial_number=gateway.serial_number if gateway else None,
        )

    @property
    def gateway(self) -> Gateway | None:
        """Return the current gateway from the coordinator, if present."""
        return self.coordinator.get_gateway(self._gateway_id)

    @property
    def available(self) -> bool:
        """Available only while the gateway exists and reports itself online."""
        gateway = self.gateway
        return super().available and gateway is not None and gateway.is_online


class OaseDeviceEntity(CoordinatorEntity[OaseDataUpdateCoordinator]):
    """Base class for OASE devices attached to a gateway (pumps, LEDs, ...)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the device entity and its device registry entry."""
        super().__init__(coordinator)
        self._gateway_id = gateway_id
        self._device_id = device_id
        device = coordinator.get_device(device_id)
        # Prefer a user-assigned name, then the OASE product name from the gateway's
        # device table ("Expert 22000"), then the bare type ("GardenPump").
        name = name_from_custom_attributes(device.custom_attributes if device else None)
        product_name = device.product_name if device else None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            via_device=(DOMAIN, gateway_id),
            manufacturer=MANUFACTURER,
            name=name or product_name or (device.device_type if device else None),
            model=product_name or (device.device_type if device else None),
            sw_version=device.software_version if device else None,
        )

    @property
    def device(self) -> Device | None:
        """Return the current attached device from the coordinator, if present."""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        """Available only while the device exists and is connected."""
        device = self.device
        return super().available and device is not None and device.is_connected
