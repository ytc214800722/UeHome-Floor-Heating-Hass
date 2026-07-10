# UeHome Floor Heating for Home Assistant

<img src="custom_components/uehome/icon.png" alt="UeHome Floor Heating" width="128">

Home Assistant custom integration for UeHome / 优e家 floor-heating thermostats.

This integration listens for local UDP state broadcasts on port `60002`, creates selected devices as Home Assistant `climate` entities, and controls only power state plus target temperature.

## Features

- Automatically discovers UeHome devices from UDP state broadcasts.
- Lets you choose which discovered devices to add.
- Requires a separate password for each selected thermostat.
- Does not show devices that were already added.
- Creates one `climate` entity per selected thermostat.
- Reads only room temperature and heating state.
- Controls only on/off and target temperature.

## Field Mapping

| Home Assistant climate value | UeHome field | Meaning |
|---|---|---|
| Current temperature | `temp` | Room temperature |
| Target temperature | `hw_temp_set` | Heating setpoint |
| HVAC mode `off` | `k_close=true` | Thermostat is off |
| HVAC mode `heat` | `k_close=false` | Thermostat is on / allowed to heat |
| HVAC action `heating` | `is_heat=true` | Thermostat is actively heating |
| HVAC action `idle` | `k_close=false` and `is_heat=false` | Thermostat is on but not currently heating |

The integration intentionally does not expose floor temperature, RSSI, mode, child lock, diagnostic codes, or other fields.

## Control Payloads

The integration sends UTF-8 JSON over UDP `60002` using the observed UeHome command shape.

Turn on:

```json
["", "SN", "set", {"k_close": false, "seq": 3, "version": 1, "p_w": "PASSWORD"}]
```

Turn off:

```json
["", "SN", "set", {"k_close": true, "seq": 3, "version": 1, "p_w": "PASSWORD"}]
```

Set target temperature:

```json
["", "SN", "set", {"hw_temp_set": 23, "seq": 3, "version": 1, "p_w": "PASSWORD"}]
```

## Installation

### HACS

1. In HACS, open **Custom repositories**.
2. Add this repository URL:

```text
https://github.com/ytc214800722/UeHome-Floor-Heating-Hass
```

3. Select **Integration** as the category.
4. Install **UeHome Floor Heating** from HACS.
5. Restart Home Assistant.
6. Go to **Settings > Devices & services > Add integration**.
7. Search for **UeHome Floor Heating**.

### Manual

1. Copy this folder into your Home Assistant config directory:

```text
custom_components/uehome
```

The final structure should look like:

```text
config/
  configuration.yaml
  custom_components/
    uehome/
      __init__.py
      brand/
        icon.png
      climate.py
      config_flow.py
      const.py
      coordinator.py
      entity.py
      manifest.json
      protocol.py
      strings.json
```

2. Restart Home Assistant.

3. Go to **Settings > Devices & services > Add integration**.

4. Search for **UeHome Floor Heating**.

## Setup Flow

1. Enter the UDP port. The default is `60002`.
2. The integration passively scans for UeHome state broadcasts.
3. Select the thermostats you want to add.
4. Enter the password for each selected thermostat.
5. Save.

The integration keeps one UDP listener and creates entities only for selected serial numbers. Other devices broadcasting on UDP `60002` are ignored.

Already-added devices are not shown again if you run the setup flow later to add more thermostats.

## Password Behavior

Device password is required for every selected thermostat.

There is no separate password-check endpoint in the observed protocol, so setup does not pre-validate passwords. Based on testing, an incorrect password makes the device ignore control commands and leave state unchanged.

## HomeKit

If you expose the entity through Home Assistant HomeKit Bridge, it appears as a heat-only thermostat:

- Off maps to `k_close=true`.
- Heat maps to `k_close=false`.
- Heating status comes from `is_heat`.
- Target temperature changes send `hw_temp_set`.

HomeKit will not show diagnostic fields because the integration does not expose them.
