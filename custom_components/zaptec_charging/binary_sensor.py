"""Binary sensors for Zaptec Charging."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecChargingConfigEntry
from .entity import ZaptecChargingEntity

SOLAR_PAUSED = BinarySensorEntityDescription(
    key="solar_paused",
    translation_key="solar_paused",
    icon="mdi:pause-circle",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecChargingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SolarPausedSensor(entry.runtime_data, SOLAR_PAUSED)])


class SolarPausedSensor(ZaptecChargingEntity, BinarySensorEntity):
    """On while solar charging is paused for lack of sun."""

    @property
    def is_on(self) -> bool:
        return self.controller.paused
