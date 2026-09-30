# Zaptec Charging

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Validate](https://github.com/GrasshopperNL/ha-zaptec-charging/actions/workflows/validate.yml/badge.svg)](https://github.com/GrasshopperNL/ha-zaptec-charging/actions/workflows/validate.yml)

Solar surplus charging for Zaptec chargers in Home Assistant, with night tariff
and forced charging, an actionable notification when the car is connected, and
a split of the charged energy into solar and grid.

> Nederlandse samenvatting: zie [onderaan](#nederlands).

This integration does not talk to the charger itself. It builds on the entities
of the official [Zaptec integration](https://www.home-assistant.io/integrations/zaptec/)
and a smart meter (for example a HomeWizard P1 meter).

## Features

- **Solar charging** on one phase. The charge current follows the solar surplus
  between a minimum and maximum current.
- **Without sun**: keep charging at the minimum current, or pause after a
  configurable period of too little surplus and resume automatically.
- **Wait for night tariff**: charging is paused and starts on three phases at a
  configurable time.
- **Forced charging** on three phases at the maximum current.
- **Nightly forced charging** at a configurable time, and forced charging when
  the car reports it is full (quick top up for climate control).
- **Actionable notification** on the phone when the car is connected.
- **Energy split**: charged energy from solar and from grid, in total and per
  day, month and year. Grid import is netted over the phases, the same way the
  smart meter bills it.
- Phase switching and current changes are only written to the charger when the
  value actually changes, which keeps cloud writes to a minimum.

## Requirements

| Entity | Example |
| --- | --- |
| Zaptec charger mode sensor | `sensor.<charger>_charger_mode` |
| Zaptec charge power sensor (W) | `sensor.<charger>_charge_power` |
| Zaptec installation available current | `number.<installation>_available_current` |
| Zaptec installation 3 to 1 phase switch current | `number.<installation>_3_to_1_phase_switch_current` |
| Smart meter power export (W) | `sensor.electricity_meter_power_production` |
| Smart meter power import (W) | `sensor.electricity_meter_power_consumption` |
| Notify service (optional) | `notify.mobile_app_<phone>` |

Home Assistant 2024.11 or newer.

## Installation

1. In HACS, open the menu (three dots) and choose **Custom repositories**.
2. Add `https://github.com/GrasshopperNL/ha-zaptec-charging` with type **Integration**.
3. Install **Zaptec Charging** and restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration** and search for
   **Zaptec Charging**.
5. Select the entities listed above.

All charging settings can be changed afterwards via **Configure** on the
integration.

## Entities

| Entity | Description |
| --- | --- |
| `select` Charging mode | Solar, wait for night tariff, forced 3-phase |
| `select` Without sun | Continue at minimum current, or stop |
| `binary_sensor` Solar charging paused | On while solar charging waits for sun |
| `sensor` Status | Disconnected, solar charging, paused, waiting for night tariff, forced |
| `sensor` Phases | 1-phase or 3-phase |
| `sensor` Solar surplus | Charge power + export - import (W) |
| `sensor` Solar surplus average | Average over the stop period (W) |
| `sensor` Charge power from grid / solar | Split of the current charge power (W) |
| `sensor` Charged energy from grid / solar | Totals (kWh), usable in the Energy dashboard |
| `sensor` Solar / Grid today, this month, this year | Period totals (kWh) |

## Settings

| Setting | Default |
| --- | --- |
| Grid voltage | 230 V |
| Minimum / maximum charge current | 6 A / 16 A |
| Stop after too little sun for | 15 min |
| Resume after enough sun for | 10 min |
| Nightly forced charging at | 01:00 |
| Night tariff starts at | 01:15 |
| Phase switch value 1-phase / 3-phase | 32 / 0 |
| Wait after phase switch | 5 s |
| Control interval | 60 s |
| Offer "Solar, otherwise stop" in the notification | off |

## How the surplus is calculated

```
surplus = charge power + grid export - grid import
```

Adding the charge power back avoids a feedback loop: raising the charge current
lowers the export, but the surplus stays the same. Solar charging is possible
when the surplus is at least `minimum current × voltage` (6 A × 230 V = 1380 W).

## Nederlands

Zonneladen voor Zaptec laders in Home Assistant. De integratie gebruikt de
entiteiten van de officiële Zaptec integratie en een slimme meter, en regelt:

- zonneladen op 1 fase, met een laadstroom die het zonneoverschot volgt
- bij te weinig zon doorladen op minimale stroom, of pauzeren en automatisch
  hervatten
- wachten op nachtstroom, geforceerd 3-fase laden en nachtelijk geforceerd laden
- een melding met laadkeuzes zodra de auto wordt aangesloten
- de geladen energie gesplitst in zon en net, totaal en per dag, maand en jaar

Installeren via HACS als custom repository (type Integratie), daarna toevoegen
via **Instellingen > Apparaten en diensten**. De interface is in het Nederlands
en Engels, afhankelijk van de taal van je Home Assistant.

## License

MIT
