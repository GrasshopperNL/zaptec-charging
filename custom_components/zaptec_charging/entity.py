"""Base entity for Zaptec Charging."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN
from .controller import ZaptecChargingController


class ZaptecChargingEntity(Entity):
    """Entity that follows the controller state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, controller: ZaptecChargingController, description: EntityDescription
    ) -> None:
        self.controller = controller
        self.entity_description = description
        entry = controller.entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GrasshopperNL",
            model="Zaptec Charging",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal, self.async_write_ha_state
            )
        )
