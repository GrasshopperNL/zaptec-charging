"""Sensors for Zaptec Charging."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZaptecChargingConfigEntry
from .const import PHASE_1P, PHASE_3P, STATUSES
from .controller import ZaptecChargingController
from .entity import ZaptecChargingEntity


@dataclass(frozen=True, kw_only=True)
class ZaptecChargingSensorDescription(SensorEntityDescription):
    """Describes a Zaptec Charging sensor."""

    value_fn: Callable[[ZaptecChargingController], float | str | None]
    last_reset_fn: Callable[[ZaptecChargingController], datetime | None] | None = None


def _power(key: str, value_fn, icon: str | None = None) -> ZaptecChargingSensorDescription:
    return ZaptecChargingSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        icon=icon,
        value_fn=value_fn,
    )


def _energy_total(source: str) -> ZaptecChargingSensorDescription:
    return ZaptecChargingSensorDescription(
        key=f"energy_{source}",
        translation_key=f"energy_{source}",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda c: round(c.energy_grid if source == "grid" else c.energy_solar, 3),
    )


def _energy_period(source: str, period: str) -> ZaptecChargingSensorDescription:
    return ZaptecChargingSensorDescription(
        key=f"energy_{source}_{period}",
        translation_key=f"energy_{source}_{period}",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda c: c.period_value(period, source),
        last_reset_fn=lambda c: c.period_start(period),
    )


SENSORS: tuple[ZaptecChargingSensorDescription, ...] = (
    _power("surplus", lambda c: c.surplus, "mdi:solar-power-variant"),
    _power("surplus_average", lambda c: c.surplus_average, "mdi:solar-power-variant-outline"),
    _power("charge_power_grid", lambda c: c.power_grid, "mdi:transmission-tower"),
    _power("charge_power_solar", lambda c: c.power_solar, "mdi:solar-power"),
    _energy_total("grid"),
    _energy_total("solar"),
    *(
        _energy_period(source, period)
        for period in ("daily", "monthly", "yearly")
        for source in ("solar", "grid")
    ),
    ZaptecChargingSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUSES,
        icon="mdi:ev-station",
        value_fn=lambda c: c.status,
    ),
    ZaptecChargingSensorDescription(
        key="phase",
        translation_key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=[PHASE_1P, PHASE_3P],
        icon="mdi:sine-wave",
        value_fn=lambda c: c.phase,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZaptecChargingConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller = entry.runtime_data
    async_add_entities(ZaptecChargingSensor(controller, d) for d in SENSORS)


class ZaptecChargingSensor(ZaptecChargingEntity, SensorEntity):
    """Sensor backed by the controller."""

    entity_description: ZaptecChargingSensorDescription

    @property
    def native_value(self) -> float | str | None:
        return self.entity_description.value_fn(self.controller)

    @property
    def last_reset(self) -> datetime | None:
        if self.entity_description.last_reset_fn is None:
            return None
        return self.entity_description.last_reset_fn(self.controller)
