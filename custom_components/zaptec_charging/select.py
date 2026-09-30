"""Select entities for Zaptec Charging."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecChargingConfigEntry
from .const import CHARGING_MODES, SOLAR_MODES
from .entity import ZaptecChargingEntity

CHARGING_MODE = SelectEntityDescription(
    key="charging_mode",
    translation_key="charging_mode",
    options=CHARGING_MODES,
    icon="mdi:ev-station",
)
SOLAR_MODE = SelectEntityDescription(
    key="solar_mode",
    translation_key="solar_mode",
    options=SOLAR_MODES,
    icon="mdi:weather-sunny-off",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecChargingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    async_add_entities(
        [
            ChargingModeSelect(controller, CHARGING_MODE),
            SolarModeSelect(controller, SOLAR_MODE),
        ]
    )


class ChargingModeSelect(ZaptecChargingEntity, SelectEntity):
    """Solar, night tariff or forced charging."""

    @property
    def current_option(self) -> str:
        return self.controller.mode

    async def async_select_option(self, option: str) -> None:
        await self.controller.async_set_mode(option)


class SolarModeSelect(ZaptecChargingEntity, SelectEntity):
    """Continue at minimal current or stop without sun."""

    @property
    def current_option(self) -> str:
        return self.controller.solar_mode

    async def async_select_option(self, option: str) -> None:
        await self.controller.async_set_solar_mode(option)
