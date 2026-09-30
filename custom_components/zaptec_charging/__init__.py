"""Zaptec Charging: solar surplus charging for Zaptec chargers."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import ZaptecChargingController

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR]

type ZaptecChargingConfigEntry = ConfigEntry[ZaptecChargingController]


async def async_setup_entry(hass: HomeAssistant, entry: ZaptecChargingConfigEntry) -> bool:
    """Set up Zaptec Charging from a config entry."""
    controller = ZaptecChargingController(hass, entry)
    await controller.async_setup()
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZaptecChargingConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_unload()
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ZaptecChargingConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)
