"""Charging logic for Zaptec Charging.

This module replaces the YAML package: helpers, template sensors, the
statistics sensor, the integration sensors, the utility meters and all
automations live here as one controller per config entry.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ACTION_FORCED,
    ACTION_NIGHT,
    ACTION_SOLAR,
    ACTION_SOLAR_STOP,
    ACTIVE_STATES,
    CONF_AVAILABLE_CURRENT,
    CONF_CHARGE_POWER,
    CONF_CHARGER_MODE,
    CONF_CONTROL_INTERVAL,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
    CONF_MAX_CURRENT,
    CONF_MIN_CURRENT,
    CONF_NIGHT_FORCED_TIME,
    CONF_NIGHT_TARIFF_TIME,
    CONF_NOTIFY_SERVICE,
    CONF_OFFER_STOP_OPTION,
    CONF_PHASE_SWITCH,
    CONF_PHASE_VALUE_1P,
    CONF_PHASE_VALUE_3P,
    CONF_PHASE_WAIT,
    CONF_RESUME_MINUTES,
    CONF_STOP_MINUTES,
    CONF_VOLTAGE,
    CONNECTED_STATES,
    DEFAULTS,
    DOMAIN,
    MODE_FORCED,
    MODE_NIGHT,
    MODE_SOLAR,
    PHASE_1P,
    PHASE_3P,
    SIGNAL_UPDATE,
    SOLAR_CONTINUE,
    SOLAR_STOP,
    STATE_DISCONNECTED,
    STATE_FINISHED,
    STATUS_DISCONNECTED,
    STATUS_FORCED,
    STATUS_SOLAR,
    STATUS_SOLAR_PAUSED,
    STATUS_WAITING_NIGHT,
    STORAGE_VERSION,
)
from .texts import text

_LOGGER = logging.getLogger(__name__)

PERIODS = ("daily", "monthly", "yearly")
SAVE_DELAY = 30


@dataclass
class PeriodBaseline:
    """Meter readings at the start of a period."""

    key: str
    start: datetime
    grid: float
    solar: float


def _period_key(period: str, now: datetime) -> str:
    if period == "daily":
        return now.strftime("%Y-%m-%d")
    if period == "monthly":
        return now.strftime("%Y-%m")
    return now.strftime("%Y")


def _period_start(period: str, now: datetime) -> datetime:
    start = dt_util.start_of_local_day(now)
    if period == "monthly":
        start = start.replace(day=1)
    elif period == "yearly":
        start = start.replace(month=1, day=1)
    return start


def _parse_time(value: str) -> tuple[int, int, int]:
    parts = [int(p) for p in str(value).split(":")]
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


class ZaptecChargingController:
    """Holds the state and runs the charging logic for one charger."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.config: dict[str, Any] = {**DEFAULTS, **entry.data, **entry.options}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._unsubs: list[CALLBACK_TYPE] = []
        self._control_task: asyncio.Task | None = None
        self._reset_task: asyncio.Task | None = None

        # Persistent state
        self.mode: str = MODE_SOLAR
        self.solar_mode: str = SOLAR_CONTINUE
        self.paused: bool = False
        self.choice_requested: bool = False
        self.energy_grid: float = 0.0
        self.energy_solar: float = 0.0
        self._baselines: dict[str, PeriodBaseline] = {}

        # Live measurements
        self.surplus: float | None = None
        self.power_grid: float | None = None
        self.power_solar: float | None = None
        self._last_sample: datetime | None = None
        self._samples: deque[tuple[datetime, float]] = deque()

        # Threshold tracking (numeric_state with "for" semantics)
        self._below_since: datetime | None = None
        self._above_since: datetime | None = None
        self._stop_fired = False
        self._resume_fired = False

        suffix = entry.entry_id
        self._actions = {
            f"{ACTION_SOLAR}_{suffix}": ACTION_SOLAR,
            f"{ACTION_SOLAR_STOP}_{suffix}": ACTION_SOLAR_STOP,
            f"{ACTION_NIGHT}_{suffix}": ACTION_NIGHT,
            f"{ACTION_FORCED}_{suffix}": ACTION_FORCED,
        }

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    @property
    def min_current(self) -> int:
        return int(self.config[CONF_MIN_CURRENT])

    @property
    def max_current(self) -> int:
        return int(self.config[CONF_MAX_CURRENT])

    @property
    def voltage(self) -> float:
        return float(self.config[CONF_VOLTAGE])

    @property
    def min_surplus(self) -> float:
        """Minimal surplus in W needed to charge at the minimal current."""
        return self.min_current * self.voltage

    @property
    def signal(self) -> str:
        return SIGNAL_UPDATE.format(self.entry.entry_id)

    def _state(self, key: str) -> str | None:
        entity_id = self.config.get(key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return state.state if state else None

    def _float_state(self, key: str) -> float | None:
        value = self._state(key)
        if value in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def charger_state(self) -> str | None:
        return self._state(CONF_CHARGER_MODE)

    @property
    def connected(self) -> bool:
        return self.charger_state in CONNECTED_STATES

    @property
    def status(self) -> str:
        if not self.connected:
            return STATUS_DISCONNECTED
        if self.mode == MODE_FORCED:
            return STATUS_FORCED
        if self.mode == MODE_NIGHT:
            return STATUS_WAITING_NIGHT
        if self.paused:
            return STATUS_SOLAR_PAUSED
        return STATUS_SOLAR

    @property
    def phase(self) -> str | None:
        value = self._float_state(CONF_PHASE_SWITCH)
        if value is None:
            return None
        if value == float(self.config[CONF_PHASE_VALUE_3P]):
            return PHASE_3P
        return PHASE_1P

    @property
    def surplus_average(self) -> float | None:
        if not self._samples:
            return None
        return round(sum(v for _, v in self._samples) / len(self._samples), 1)

    def period_value(self, period: str, source: str) -> float | None:
        baseline = self._baselines.get(period)
        if baseline is None:
            return None
        total = self.energy_grid if source == "grid" else self.energy_solar
        start = baseline.grid if source == "grid" else baseline.solar
        return round(max(total - start, 0.0), 3)

    def period_start(self, period: str) -> datetime | None:
        baseline = self._baselines.get(period)
        return baseline.start if baseline else None

    # ------------------------------------------------------------------
    # Setup and teardown
    # ------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Restore state and start listening."""
        await self._async_restore()
        self._check_periods(dt_util.now())

        power_entities = [
            self.config[CONF_CHARGE_POWER],
            self.config[CONF_GRID_EXPORT],
            self.config[CONF_GRID_IMPORT],
        ]
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, power_entities, self._handle_power_event
            )
        )
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.config[CONF_CHARGER_MODE]], self._handle_charger_event
            )
        )
        self._unsubs.append(
            async_track_state_change_event(
                self.hass, [self.config[CONF_PHASE_SWITCH]], self._handle_phase_event
            )
        )
        self._unsubs.append(
            self.hass.bus.async_listen(
                "mobile_app_notification_action", self._handle_notification_action
            )
        )

        hour, minute, second = _parse_time(self.config[CONF_NIGHT_TARIFF_TIME])
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._handle_night_tariff_time,
                hour=hour,
                minute=minute,
                second=second,
            )
        )
        hour, minute, second = _parse_time(self.config[CONF_NIGHT_FORCED_TIME])
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._handle_night_forced_time,
                hour=hour,
                minute=minute,
                second=second,
            )
        )
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._handle_midnight, hour=0, minute=0, second=0
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._handle_interval,
                timedelta(seconds=int(self.config[CONF_CONTROL_INTERVAL])),
            )
        )

        # Start with a first calculation from the current states
        self._process_power(dt_util.utcnow())

    async def async_unload(self) -> None:
        """Stop listening and save state."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_control()
        if self._reset_task and not self._reset_task.done():
            self._reset_task.cancel()
        await self._store.async_save(self._data_to_save())

    async def _async_restore(self) -> None:
        data = await self._store.async_load() or {}
        self.mode = data.get("mode", MODE_SOLAR)
        self.solar_mode = data.get("solar_mode", SOLAR_CONTINUE)
        self.paused = data.get("paused", False)
        self.choice_requested = data.get("choice_requested", False)
        self.energy_grid = float(data.get("energy_grid", 0.0))
        self.energy_solar = float(data.get("energy_solar", 0.0))
        for period, raw in data.get("baselines", {}).items():
            start = dt_util.parse_datetime(raw["start"])
            if start is None:
                continue
            self._baselines[period] = PeriodBaseline(
                key=raw["key"], start=start, grid=raw["grid"], solar=raw["solar"]
            )

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "solar_mode": self.solar_mode,
            "paused": self.paused,
            "choice_requested": self.choice_requested,
            "energy_grid": self.energy_grid,
            "energy_solar": self.energy_solar,
            "baselines": {
                period: {
                    "key": b.key,
                    "start": b.start.isoformat(),
                    "grid": b.grid,
                    "solar": b.solar,
                }
                for period, b in self._baselines.items()
            },
        }

    @callback
    def _changed(self) -> None:
        """Notify entities and schedule saving."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)
        async_dispatcher_send(self.hass, self.signal)

    # ------------------------------------------------------------------
    # Public setters used by the select entities
    # ------------------------------------------------------------------
    async def async_set_mode(self, mode: str) -> None:
        """Select a charging mode from the UI (clears a solar pause)."""
        self.mode = mode
        self.paused = False
        self._changed()
        self._request_control()

    async def async_set_solar_mode(self, solar_mode: str) -> None:
        """Select what happens when there is not enough sun."""
        self.solar_mode = solar_mode
        self._changed()
        if solar_mode == SOLAR_STOP:
            await self._async_try_stop(selected=True)
        self._request_control()

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------
    @callback
    def _handle_power_event(self, event: Event[EventStateChangedData]) -> None:
        self._process_power(dt_util.utcnow())

    @callback
    def _process_power(self, now: datetime) -> None:
        charge = self._float_state(CONF_CHARGE_POWER)
        export = self._float_state(CONF_GRID_EXPORT)
        imported = self._float_state(CONF_GRID_IMPORT)

        # Start a new day, month or year before adding energy
        self._check_periods(dt_util.now())

        # Left Riemann sum over the previous interval
        if self._last_sample is not None:
            hours = (now - self._last_sample).total_seconds() / 3600
            if self.power_grid is not None:
                self.energy_grid += self.power_grid * hours / 1000
            if self.power_solar is not None:
                self.energy_solar += self.power_solar * hours / 1000
        self._last_sample = now

        # Surplus: charge power + export - import (no feedback loop)
        self.surplus = round((charge or 0) + (export or 0) - (imported or 0))

        # Split charge power in grid and solar. Import is netted over the
        # phases, the same way the smart meter bills it.
        if charge is None or export is None or imported is None:
            self.power_grid = None
            self.power_solar = None
        else:
            net_import = max(imported - export, 0)
            self.power_grid = round(min(charge, net_import))
            self.power_solar = round(max(charge - net_import, 0))

        # Rolling window for the average surplus
        self._samples.append((now, self.surplus))
        window = timedelta(minutes=int(self.config[CONF_STOP_MINUTES]))
        while len(self._samples) > 1 and now - self._samples[0][0] > window:
            self._samples.popleft()

        self._evaluate_thresholds(now)
        self._changed()

    @callback
    def _check_periods(self, now_local: datetime) -> None:
        for period in PERIODS:
            key = _period_key(period, now_local)
            baseline = self._baselines.get(period)
            if baseline is None or baseline.key != key:
                self._baselines[period] = PeriodBaseline(
                    key=key,
                    start=_period_start(period, now_local),
                    grid=self.energy_grid,
                    solar=self.energy_solar,
                )

    @callback
    def _evaluate_thresholds(self, now: datetime) -> None:
        if self.surplus is None:
            return
        min_surplus = self.min_surplus

        if self.surplus < min_surplus:
            self._above_since = None
            self._resume_fired = False
            if self._below_since is None:
                self._below_since = now
            if not self._stop_fired and now - self._below_since >= timedelta(
                minutes=int(self.config[CONF_STOP_MINUTES])
            ):
                self._stop_fired = True
                self.entry.async_create_background_task(
                    self.hass, self._async_try_stop(selected=False), f"{DOMAIN}_stop"
                )
        elif self.surplus > min_surplus:
            self._below_since = None
            self._stop_fired = False
            if self._above_since is None:
                self._above_since = now
            if not self._resume_fired and now - self._above_since >= timedelta(
                minutes=int(self.config[CONF_RESUME_MINUTES])
            ):
                self._resume_fired = True
                self.entry.async_create_background_task(
                    self.hass, self._async_try_resume(), f"{DOMAIN}_resume"
                )
        else:
            self._below_since = None
            self._above_since = None
            self._stop_fired = False
            self._resume_fired = False

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    @callback
    def _handle_phase_event(self, event: Event[EventStateChangedData]) -> None:
        async_dispatcher_send(self.hass, self.signal)

    @callback
    def _handle_charger_event(self, event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        old_state = old.state if old else None
        new_state = new.state if new else None

        # Car connected: ask once how to charge
        if (
            old_state == STATE_DISCONNECTED
            and new_state not in (STATE_UNKNOWN, STATE_UNAVAILABLE, None)
            and not self.choice_requested
        ):
            self.choice_requested = True
            self.entry.async_create_background_task(
                self.hass, self._async_send_choice(), f"{DOMAIN}_choice"
            )

        # Charging finished: switch to forced for fast top up (climate control)
        if new_state == STATE_FINISHED and self.mode != MODE_NIGHT and not self.paused:
            self.mode = MODE_FORCED

        # Car disconnected: reset everything
        if new_state == STATE_DISCONNECTED:
            self._cancel_control()
            self.mode = MODE_SOLAR
            self.solar_mode = SOLAR_CONTINUE
            self.paused = False
            self.choice_requested = False
            self._reset_task = self.entry.async_create_background_task(
                self.hass, self._async_reset_charger(), f"{DOMAIN}_reset"
            )
            self._changed()
            return

        self._changed()
        self._request_control()

    async def _handle_notification_action(self, event: Event) -> None:
        action = self._actions.get(event.data.get("action"))
        if action is None:
            return

        self.paused = False
        if action == ACTION_FORCED:
            self.mode = MODE_FORCED
        elif action == ACTION_NIGHT:
            self.mode = MODE_NIGHT
            await self._async_notify(
                text(self.hass, "night_title"),
                text(
                    self.hass,
                    "night_message",
                    night_time=self._night_time_label(),
                    max_current=self.max_current,
                ),
            )
        else:
            self.solar_mode = SOLAR_STOP if action == ACTION_SOLAR_STOP else SOLAR_CONTINUE
            self.mode = MODE_SOLAR
        self._changed()
        if action == ACTION_SOLAR_STOP:
            await self._async_try_stop(selected=True)
        self._request_control()

    @callback
    def _handle_night_tariff_time(self, now: datetime) -> None:
        if self.mode == MODE_NIGHT and self.connected:
            self.mode = MODE_FORCED
            self._changed()
            self._request_control()

    @callback
    def _handle_night_forced_time(self, now: datetime) -> None:
        if not self.connected or self.mode == MODE_NIGHT or self.paused:
            return
        if self.mode == MODE_SOLAR and self.solar_mode == SOLAR_STOP:
            return
        self.mode = MODE_FORCED
        self._changed()
        self._request_control()

    @callback
    def _handle_midnight(self, now: datetime) -> None:
        self._check_periods(dt_util.now())
        self._changed()

    @callback
    def _handle_interval(self, now: datetime) -> None:
        # Keep the threshold timers running when the meters stop reporting
        self._evaluate_thresholds(dt_util.utcnow())
        self._request_control()

    # ------------------------------------------------------------------
    # Stop and resume solar charging
    # ------------------------------------------------------------------
    async def _async_try_stop(self, selected: bool) -> None:
        if self.paused or self.mode != MODE_SOLAR or self.solar_mode != SOLAR_STOP:
            return
        if self.charger_state not in ACTIVE_STATES:
            return
        if selected:
            average = self.surplus_average
            if average is None or average >= self.min_surplus:
                return

        self._cancel_control()
        self.paused = True
        self._changed()
        await self._async_set_number(CONF_AVAILABLE_CURRENT, 0)
        message = (
            text(
                self.hass,
                "stopped_selected",
                minutes=int(self.config[CONF_STOP_MINUTES]),
            )
            if selected
            else text(self.hass, "stopped_no_sun")
        )
        await self._async_notify(text(self.hass, "stopped_title"), message)

    async def _async_try_resume(self) -> None:
        if not self.paused or self.mode != MODE_SOLAR or not self.connected:
            return
        self._cancel_control()
        self.paused = False
        self._changed()
        await self._async_set_number(CONF_AVAILABLE_CURRENT, self.min_current)
        await self._async_notify(
            text(self.hass, "resumed_title"), text(self.hass, "resumed_message")
        )
        self._request_control()

    # ------------------------------------------------------------------
    # Charger control
    # ------------------------------------------------------------------
    @callback
    def _cancel_control(self) -> None:
        if self._control_task and not self._control_task.done():
            self._control_task.cancel()
        self._control_task = None

    @callback
    def _request_control(self) -> None:
        """Run the control logic; a newer request replaces a running one."""
        self._cancel_control()
        self._control_task = self.entry.async_create_background_task(
            self.hass, self._async_control(), f"{DOMAIN}_control"
        )

    async def _async_control(self) -> None:
        if not self.connected:
            return

        if self.mode == MODE_NIGHT:
            await self._async_set_number(CONF_AVAILABLE_CURRENT, 0)
            return

        if self.mode == MODE_FORCED:
            await self._async_ensure_phase(self.config[CONF_PHASE_VALUE_3P])
            await self._async_set_number(CONF_AVAILABLE_CURRENT, self.max_current)
            return

        # Solar charging on one phase
        await self._async_ensure_phase(self.config[CONF_PHASE_VALUE_1P])
        if self.paused:
            return
        amps = math.floor((self.surplus or 0) / self.voltage)
        amps = min(max(amps, self.min_current), self.max_current)
        await self._async_set_number(CONF_AVAILABLE_CURRENT, amps)

    async def _async_reset_charger(self) -> None:
        await self._async_set_number(
            CONF_PHASE_SWITCH, self.config[CONF_PHASE_VALUE_1P], force=True
        )
        await asyncio.sleep(int(self.config[CONF_PHASE_WAIT]))
        await self._async_set_number(
            CONF_AVAILABLE_CURRENT, self.min_current, force=True
        )

    async def _async_ensure_phase(self, value: float) -> None:
        """Switch phase only when needed, then wait for the charger."""
        if await self._async_set_number(CONF_PHASE_SWITCH, value):
            await asyncio.sleep(int(self.config[CONF_PHASE_WAIT]))

    async def _async_set_number(
        self, key: str, value: float, force: bool = False
    ) -> bool:
        """Write a number entity. Returns True when a write was done.

        Without force, nothing is written when the value is already set,
        which avoids needless (cloud) writes to the charger.
        """
        if not force and self._float_state(key) == float(value):
            return False
        try:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self.config[key], "value": value},
                blocking=True,
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Could not set %s to %s: %s", self.config[key], value, err)
            return False
        return True

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def _night_time_label(self) -> str:
        hour, minute, _ = _parse_time(self.config[CONF_NIGHT_TARIFF_TIME])
        return f"{hour:02d}:{minute:02d}"

    async def _async_send_choice(self) -> None:
        suffix = self.entry.entry_id
        actions = [
            {
                "action": f"{ACTION_SOLAR}_{suffix}",
                "title": text(self.hass, "action_solar", min_current=self.min_current),
            }
        ]
        if self.config[CONF_OFFER_STOP_OPTION]:
            actions.append(
                {
                    "action": f"{ACTION_SOLAR_STOP}_{suffix}",
                    "title": text(self.hass, "action_solar_stop"),
                }
            )
        actions += [
            {
                "action": f"{ACTION_NIGHT}_{suffix}",
                "title": text(
                    self.hass, "action_night", night_time=self._night_time_label()
                ),
            },
            {
                "action": f"{ACTION_FORCED}_{suffix}",
                "title": text(self.hass, "action_forced"),
            },
        ]
        await self._async_notify(
            text(self.hass, "choice_title"),
            text(self.hass, "choice_message"),
            {"tag": f"{DOMAIN}_{suffix}", "actions": actions},
        )

    async def _async_notify(
        self, title: str, message: str, data: dict[str, Any] | None = None
    ) -> None:
        service = self.config.get(CONF_NOTIFY_SERVICE)
        if not service:
            return
        service = service.removeprefix("notify.")
        payload: dict[str, Any] = {"title": title, "message": message}
        if data:
            payload["data"] = data
        try:
            await self.hass.services.async_call("notify", service, payload)
        except HomeAssistantError as err:
            _LOGGER.warning("Could not send notification via notify.%s: %s", service, err)
