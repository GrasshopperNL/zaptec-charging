"""Behaviour tests for Zaptec Charging."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.zaptec_charging.const import (
    ACTION_FORCED,
    ACTION_NIGHT,
    CONF_AVAILABLE_CURRENT,
    CONF_CHARGE_POWER,
    CONF_CHARGER_MODE,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_NOTIFY_SERVICE,
    CONF_PHASE_SWITCH,
    DOMAIN,
)

CHARGER = "sensor.charger_mode"
POWER = "sensor.charge_power"
CURRENT = "number.available_current"
PHASE = "number.phase_switch"
EXPORT = "sensor.p1_export"
IMPORT = "sensor.p1_import"

DATA = {
    CONF_CHARGER_MODE: CHARGER,
    CONF_CHARGE_POWER: POWER,
    CONF_AVAILABLE_CURRENT: CURRENT,
    CONF_PHASE_SWITCH: PHASE,
    CONF_GRID_EXPORT: EXPORT,
    CONF_GRID_IMPORT: IMPORT,
    CONF_NOTIFY_SERVICE: "notify.phone",
}


def _set(hass: HomeAssistant, charger="disconnected", power=0, export=0, imp=0,
         current=6, phase=32) -> None:
    hass.states.async_set(CHARGER, charger)
    hass.states.async_set(POWER, power)
    hass.states.async_set(EXPORT, export)
    hass.states.async_set(IMPORT, imp)
    hass.states.async_set(CURRENT, current)
    hass.states.async_set(PHASE, phase)


@pytest.fixture
async def setup(hass: HomeAssistant):
    """Set up the integration with a mocked number and notify service."""
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    hass.config.language = "nl"
    _set(hass)
    numbers = async_mock_service(hass, "number", "set_value")
    notes = async_mock_service(hass, "notify", "phone")
    entry = MockConfigEntry(domain=DOMAIN, title="Zaptec", data=DATA, unique_id=CURRENT)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, numbers, notes


def _writes(numbers, entity_id):
    return [c.data["value"] for c in numbers if c.data["entity_id"] == entity_id]


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Laadpaal", **DATA}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Laadpaal"


async def test_options_flow_validation(hass: HomeAssistant, setup) -> None:
    entry, _, _ = setup
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    options = {
        **DATA,
        "voltage": 230, "min_current": 10, "max_current": 8,
        "stop_minutes": 15, "resume_minutes": 10,
        "night_forced_time": "01:00:00", "night_tariff_time": "01:15:00",
        "phase_value_1p": 32, "phase_value_3p": 0, "phase_wait_seconds": 5,
        "control_interval_seconds": 60, "offer_stop_option": False,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    assert result["errors"] == {"max_current": "max_below_min"}
    options["max_current"] = 16
    result = await hass.config_entries.options.async_configure(result["flow_id"], options)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_entities_created(hass: HomeAssistant, setup) -> None:
    ids = hass.states.async_entity_ids()
    for expected in (
        "select.zaptec_laadmodus",
        "select.zaptec_zonder_zon",
        "binary_sensor.zaptec_zonneladen_gepauzeerd",
        "sensor.zaptec_zonneoverschot",
        "sensor.zaptec_zon_vandaag",
        "sensor.zaptec_status",
        "sensor.zaptec_fasen",
    ):
        assert expected in ids, expected


async def test_surplus_and_split(hass: HomeAssistant, setup) -> None:
    hass.states.async_set(POWER, 3000)
    hass.states.async_set(EXPORT, 0)
    hass.states.async_set(IMPORT, 1000)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.zaptec_zonneoverschot").state == "2000"
    assert hass.states.get("sensor.zaptec_laadvermogen_uit_net").state == "1000"
    assert hass.states.get("sensor.zaptec_laadvermogen_uit_zon").state == "2000"


async def test_connect_sends_choice_and_solar_regulates(
    hass: HomeAssistant, setup
) -> None:
    entry, numbers, notes = setup
    hass.states.async_set(CHARGER, "connected_requesting")
    await hass.async_block_till_done()
    assert len(notes) == 1
    actions = [a["action"] for a in notes[0].data["data"]["actions"]]
    assert actions == [
        f"ZAPTEC_CHARGING_SOLAR_{entry.entry_id}",
        f"{ACTION_NIGHT}_{entry.entry_id}",
        f"{ACTION_FORCED}_{entry.entry_id}",
    ]

    # 2100 W surplus (charging 1400 + export 700) -> 9 A, phase already 1-phase
    hass.states.async_set(POWER, 1400)
    hass.states.async_set(EXPORT, 700)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _writes(numbers, PHASE) == []
    assert _writes(numbers, CURRENT)[-1] == 9


async def test_forced_choice_switches_phase_once(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, numbers, _ = setup
    hass.states.async_set(CHARGER, "connected_charging")
    await hass.async_block_till_done()
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"{ACTION_FORCED}_{entry.entry_id}"}
    )
    await hass.async_block_till_done()
    assert _writes(numbers, PHASE) == [0]
    hass.states.async_set(PHASE, 0)
    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _writes(numbers, CURRENT)[-1] == 16
    assert hass.states.get("sensor.zaptec_status").state == "forced"


async def test_night_choice_pauses_and_starts(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, numbers, notes = setup
    freezer.move_to("2026-09-30 22:00:00+02:00")
    hass.states.async_set(CHARGER, "connected_charging")
    await hass.async_block_till_done()
    hass.bus.async_fire(
        "mobile_app_notification_action", {"action": f"{ACTION_NIGHT}_{entry.entry_id}"}
    )
    await hass.async_block_till_done()
    assert _writes(numbers, CURRENT)[-1] == 0
    assert notes[-1].data["title"] == "Wachten op nachtstroom"

    freezer.move_to("2026-10-01 01:15:00+02:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("select.zaptec_laadmodus").state == "forced"


async def test_stop_and_resume_without_sun(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, numbers, notes = setup
    hass.states.async_set(CHARGER, "connected_charging")
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.zaptec_zonder_zon", "option": "stop_without_sun"},
        blocking=True,
    )
    # Too little sun for 15 minutes
    hass.states.async_set(POWER, 1380)
    hass.states.async_set(IMPORT, 500)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.zaptec_zonneladen_gepauzeerd").state == "on"
    assert _writes(numbers, CURRENT)[-1] == 0
    assert notes[-1].data["title"] == "Zonneladen gestopt"

    # Enough sun for 10 minutes
    hass.states.async_set(POWER, 0)
    hass.states.async_set(IMPORT, 0)
    hass.states.async_set(EXPORT, 2000)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.zaptec_zonneladen_gepauzeerd").state == "off"
    assert notes[-1].data["title"] == "Zonneladen hervat"


async def test_disconnect_resets(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    entry, numbers, _ = setup
    hass.states.async_set(CHARGER, "connected_charging")
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": "select.zaptec_laadmodus", "option": "forced"},
        blocking=True,
    )
    hass.states.async_set(CHARGER, "disconnected")
    await hass.async_block_till_done()
    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("select.zaptec_laadmodus").state == "solar"
    assert _writes(numbers, PHASE)[-1] == 32
    assert _writes(numbers, CURRENT)[-1] == 6


async def test_energy_integration(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-09-30 12:00:00+02:00")
    hass.states.async_set(POWER, 2000)
    hass.states.async_set(EXPORT, 1000)
    await hass.async_block_till_done()
    freezer.tick(timedelta(hours=1))
    hass.states.async_set(POWER, 2001)
    await hass.async_block_till_done()
    assert float(hass.states.get("sensor.zaptec_zon_vandaag").state) == pytest.approx(2.0, 0.01)
    assert float(hass.states.get("sensor.zaptec_net_vandaag").state) == 0
