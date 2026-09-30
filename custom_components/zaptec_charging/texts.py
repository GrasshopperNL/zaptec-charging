"""Notification texts in Dutch and English."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

TEXTS: dict[str, dict[str, str]] = {
    "nl": {
        "choice_title": "Auto aangesloten",
        "choice_message": "Hoe wil je laden?",
        "action_solar": "Zon, daarna {min_current}A",
        "action_solar_stop": "Zon, anders stop",
        "action_night": "Wachten tot {night_time}",
        "action_forced": "Geforceerd 3-fase",
        "night_title": "Wachten op nachtstroom",
        "night_message": "Laden is gepauzeerd, om {night_time} start 3-fase {max_current}A",
        "stopped_title": "Zonneladen gestopt",
        "stopped_selected": (
            "De afgelopen {minutes} minuten was er onvoldoende zonneoverschot, "
            "laden is gepauzeerd tot er weer genoeg zon is"
        ),
        "stopped_no_sun": "Geen zonneoverschot meer, laden is gepauzeerd",
        "resumed_title": "Zonneladen hervat",
        "resumed_message": "Er is weer voldoende zonneoverschot, laden gaat verder",
    },
    "en": {
        "choice_title": "Car connected",
        "choice_message": "How do you want to charge?",
        "action_solar": "Solar, then {min_current}A",
        "action_solar_stop": "Solar, otherwise stop",
        "action_night": "Wait until {night_time}",
        "action_forced": "Forced 3-phase",
        "night_title": "Waiting for night tariff",
        "night_message": "Charging is paused, 3-phase {max_current}A starts at {night_time}",
        "stopped_title": "Solar charging stopped",
        "stopped_selected": (
            "There was not enough solar surplus during the last {minutes} minutes, "
            "charging is paused until there is enough sun again"
        ),
        "stopped_no_sun": "No solar surplus left, charging is paused",
        "resumed_title": "Solar charging resumed",
        "resumed_message": "There is enough solar surplus again, charging continues",
    },
}


def text(hass: HomeAssistant, key: str, **kwargs: object) -> str:
    """Return a notification text in the language of the installation."""
    language = "nl" if (hass.config.language or "").startswith("nl") else "en"
    return TEXTS[language][key].format(**kwargs)
