"""Select platform for the OASE pump flow-control shows."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pyoase import OaseError, OaseGatewayOfflineError, onet

from .const import DOMAIN
from .coordinator import OaseConfigEntry, OaseDataUpdateCoordinator
from .entity import OaseDeviceEntity

_MODE_BY_NAME = {name: mode for mode, name in onet.PUMP_SHOW_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OaseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a flow-control show selector for each attached pump."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        OasePumpShowSelect(coordinator, gateway.id, device.id)
        for gateway in coordinator.data.gateways
        for device in gateway.devices
        if device.id is not None
        and device.device_number is not None
        and device.pump_state is not None
    )


class OasePumpShowSelect(OaseDeviceEntity, SelectEntity):
    """The pump's flow-control "show" program (Wild, Calm, Splashy, …, or Off).

    Reads from ``dmxPumpState`` (``fcMode`` + ``fcStatus``), which the cloud keeps
    current for this feature; writes go through the 0x5000 show packet.
    """

    _attr_translation_key = "pump_show"
    _attr_options = list(onet.PUMP_SHOW_NAMES.values())

    def __init__(
        self,
        coordinator: OaseDataUpdateCoordinator,
        gateway_id: str,
        device_id: str,
    ) -> None:
        """Initialise the pump-show selector."""
        super().__init__(coordinator, gateway_id, device_id)
        self._attr_unique_id = f"{device_id}_pump_show"

    @property
    def current_option(self) -> str | None:
        """Return the active show, or "Off" when no show is running."""
        device = self.device
        if device is None or device.pump_state is None:
            return None
        state = device.pump_state
        if not state.show_active:
            return onet.PUMP_SHOW_NAMES[0]  # "Off"
        return onet.PUMP_SHOW_NAMES.get(state.fc_mode or 0)

    async def async_select_option(self, option: str) -> None:
        """Start the chosen show, or turn shows off."""
        mode = _MODE_BY_NAME.get(option)
        if mode is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            )
        try:
            await self.coordinator.client.async_set_pump_show(self._gateway_id, mode)
        except OaseGatewayOfflineError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="gateway_offline"
            ) from err
        except OaseError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from err
        self.coordinator.apply_pump_show(self._device_id, mode)
        await self.coordinator.async_request_refresh()
