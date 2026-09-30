"""Config flow for Zaptec Charging."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
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
    DEFAULTS,
    DOMAIN,
)

ENTITY_KEYS = (
    CONF_CHARGER_MODE,
    CONF_CHARGE_POWER,
    CONF_AVAILABLE_CURRENT,
    CONF_PHASE_SWITCH,
    CONF_GRID_EXPORT,
    CONF_GRID_IMPORT,
)


def _notify_options(hass: HomeAssistant) -> list[str]:
    services = hass.services.async_services_for_domain("notify")
    skip = ("send_message", "persistent_notification")
    return sorted(f"notify.{name}" for name in services if name not in skip)


def _entities_schema(hass: HomeAssistant, defaults: dict[str, Any]) -> dict:
    def entity(domain: str, device_class: str | None = None):
        config = selector.EntitySelectorConfig(domain=domain)
        if device_class:
            config = selector.EntitySelectorConfig(domain=domain, device_class=device_class)
        return selector.EntitySelector(config)

    def req(key: str):
        if key in defaults:
            return vol.Required(key, default=defaults[key])
        return vol.Required(key)

    notify_default = defaults.get(CONF_NOTIFY_SERVICE)
    notify_key = (
        vol.Optional(CONF_NOTIFY_SERVICE, description={"suggested_value": notify_default})
    )
    return {
        req(CONF_CHARGER_MODE): entity("sensor"),
        req(CONF_CHARGE_POWER): entity("sensor", "power"),
        req(CONF_AVAILABLE_CURRENT): entity("number"),
        req(CONF_PHASE_SWITCH): entity("number"),
        req(CONF_GRID_EXPORT): entity("sensor", "power"),
        req(CONF_GRID_IMPORT): entity("sensor", "power"),
        notify_key: selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_notify_options(hass),
                custom_value=True,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
    }


def _number(min_value: float, max_value: float, step: float = 1, unit: str | None = None):
    config: dict[str, Any] = {
        "min": min_value,
        "max": max_value,
        "step": step,
        "mode": selector.NumberSelectorMode.BOX,
    }
    if unit:
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(selector.NumberSelectorConfig(**config))


def _tuning_schema(defaults: dict[str, Any]) -> dict:
    def opt(key: str):
        return vol.Required(key, default=defaults.get(key, DEFAULTS[key]))

    return {
        opt(CONF_VOLTAGE): _number(100, 400, unit="V"),
        opt(CONF_MIN_CURRENT): _number(6, 32, unit="A"),
        opt(CONF_MAX_CURRENT): _number(6, 32, unit="A"),
        opt(CONF_STOP_MINUTES): _number(1, 120, unit="min"),
        opt(CONF_RESUME_MINUTES): _number(1, 120, unit="min"),
        opt(CONF_NIGHT_FORCED_TIME): selector.TimeSelector(),
        opt(CONF_NIGHT_TARIFF_TIME): selector.TimeSelector(),
        opt(CONF_PHASE_VALUE_1P): _number(0, 32),
        opt(CONF_PHASE_VALUE_3P): _number(0, 32),
        opt(CONF_PHASE_WAIT): _number(0, 60, unit="s"),
        opt(CONF_CONTROL_INTERVAL): _number(10, 600, unit="s"),
        opt(CONF_OFFER_STOP_OPTION): selector.BooleanSelector(),
    }


def _validate_tuning(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if user_input[CONF_MIN_CURRENT] > user_input[CONF_MAX_CURRENT]:
        errors[CONF_MAX_CURRENT] = "max_below_min"
    if user_input[CONF_PHASE_VALUE_1P] == user_input[CONF_PHASE_VALUE_3P]:
        errors[CONF_PHASE_VALUE_3P] = "phase_values_equal"
    return errors


class ZaptecChargingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_AVAILABLE_CURRENT])
            self._abort_if_unique_id_configured()
            name = user_input.pop(CONF_NAME)
            return self.async_create_entry(title=name, data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Zaptec Charging"): str,
                **_entities_schema(self.hass, {}),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ZaptecChargingOptionsFlow()


class ZaptecChargingOptionsFlow(OptionsFlow):
    """Change entities and tuning after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            errors = _validate_tuning(user_input)
            if not errors:
                if CONF_NOTIFY_SERVICE not in user_input:
                    user_input[CONF_NOTIFY_SERVICE] = ""
                return self.async_create_entry(data=user_input)
            current = {**current, **user_input}

        schema = vol.Schema(
            {
                **_entities_schema(self.hass, current),
                **_tuning_schema(current),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
