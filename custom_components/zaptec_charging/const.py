"""Constants for Zaptec Charging."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "zaptec_charging"

# Config entry data: entities of the installation
CONF_CHARGER_MODE: Final = "charger_mode_entity"
CONF_CHARGE_POWER: Final = "charge_power_entity"
CONF_AVAILABLE_CURRENT: Final = "available_current_entity"
CONF_PHASE_SWITCH: Final = "phase_switch_entity"
CONF_GRID_EXPORT: Final = "grid_export_entity"
CONF_GRID_IMPORT: Final = "grid_import_entity"
CONF_NOTIFY_SERVICE: Final = "notify_service"

# Options: tuning
CONF_VOLTAGE: Final = "voltage"
CONF_MIN_CURRENT: Final = "min_current"
CONF_MAX_CURRENT: Final = "max_current"
CONF_STOP_MINUTES: Final = "stop_minutes"
CONF_RESUME_MINUTES: Final = "resume_minutes"
CONF_NIGHT_FORCED_TIME: Final = "night_forced_time"
CONF_NIGHT_TARIFF_TIME: Final = "night_tariff_time"
CONF_PHASE_VALUE_1P: Final = "phase_value_1p"
CONF_PHASE_VALUE_3P: Final = "phase_value_3p"
CONF_PHASE_WAIT: Final = "phase_wait_seconds"
CONF_CONTROL_INTERVAL: Final = "control_interval_seconds"
CONF_OFFER_STOP_OPTION: Final = "offer_stop_option"

DEFAULT_VOLTAGE: Final = 230
DEFAULT_MIN_CURRENT: Final = 6
DEFAULT_MAX_CURRENT: Final = 16
DEFAULT_STOP_MINUTES: Final = 15
DEFAULT_RESUME_MINUTES: Final = 10
DEFAULT_NIGHT_FORCED_TIME: Final = "01:00:00"
DEFAULT_NIGHT_TARIFF_TIME: Final = "01:15:00"
DEFAULT_PHASE_VALUE_1P: Final = 32
DEFAULT_PHASE_VALUE_3P: Final = 0
DEFAULT_PHASE_WAIT: Final = 5
DEFAULT_CONTROL_INTERVAL: Final = 60
DEFAULT_OFFER_STOP_OPTION: Final = False

DEFAULTS: Final = {
    CONF_VOLTAGE: DEFAULT_VOLTAGE,
    CONF_MIN_CURRENT: DEFAULT_MIN_CURRENT,
    CONF_MAX_CURRENT: DEFAULT_MAX_CURRENT,
    CONF_STOP_MINUTES: DEFAULT_STOP_MINUTES,
    CONF_RESUME_MINUTES: DEFAULT_RESUME_MINUTES,
    CONF_NIGHT_FORCED_TIME: DEFAULT_NIGHT_FORCED_TIME,
    CONF_NIGHT_TARIFF_TIME: DEFAULT_NIGHT_TARIFF_TIME,
    CONF_PHASE_VALUE_1P: DEFAULT_PHASE_VALUE_1P,
    CONF_PHASE_VALUE_3P: DEFAULT_PHASE_VALUE_3P,
    CONF_PHASE_WAIT: DEFAULT_PHASE_WAIT,
    CONF_CONTROL_INTERVAL: DEFAULT_CONTROL_INTERVAL,
    CONF_OFFER_STOP_OPTION: DEFAULT_OFFER_STOP_OPTION,
}

# Charger states reported by the Zaptec integration
STATE_DISCONNECTED: Final = "disconnected"
STATE_REQUESTING: Final = "connected_requesting"
STATE_CHARGING: Final = "connected_charging"
STATE_FINISHED: Final = "connected_finished"
CONNECTED_STATES: Final = (STATE_REQUESTING, STATE_CHARGING, STATE_FINISHED)
ACTIVE_STATES: Final = (STATE_REQUESTING, STATE_CHARGING)

# Charging mode (select entity)
MODE_SOLAR: Final = "solar"
MODE_NIGHT: Final = "night_tariff"
MODE_FORCED: Final = "forced"
CHARGING_MODES: Final = [MODE_SOLAR, MODE_NIGHT, MODE_FORCED]

# Solar behaviour when there is not enough sun (select entity)
SOLAR_CONTINUE: Final = "continue_min_current"
SOLAR_STOP: Final = "stop_without_sun"
SOLAR_MODES: Final = [SOLAR_CONTINUE, SOLAR_STOP]

# Status sensor values
STATUS_FORCED: Final = "forced"
STATUS_WAITING_NIGHT: Final = "waiting_night_tariff"
STATUS_SOLAR: Final = "solar"
STATUS_SOLAR_PAUSED: Final = "solar_paused"
STATUS_DISCONNECTED: Final = "disconnected"
STATUSES: Final = [
    STATUS_DISCONNECTED,
    STATUS_SOLAR,
    STATUS_SOLAR_PAUSED,
    STATUS_WAITING_NIGHT,
    STATUS_FORCED,
]

PHASE_1P: Final = "single_phase"
PHASE_3P: Final = "three_phase"

# Notification actions (suffixed with the config entry id)
ACTION_SOLAR: Final = "ZAPTEC_CHARGING_SOLAR"
ACTION_SOLAR_STOP: Final = "ZAPTEC_CHARGING_SOLAR_STOP"
ACTION_NIGHT: Final = "ZAPTEC_CHARGING_NIGHT"
ACTION_FORCED: Final = "ZAPTEC_CHARGING_FORCED"

STORAGE_VERSION: Final = 1

SIGNAL_UPDATE: Final = f"{DOMAIN}_update_{{}}"
