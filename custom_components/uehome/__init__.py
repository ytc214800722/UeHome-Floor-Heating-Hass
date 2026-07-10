"""UeHome floor-heating integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_PASSWORDS, CONF_DEVICES, DEFAULT_PORT, DOMAIN
from .coordinator import UeHomeRuntime

PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UeHome from a config entry."""

    runtime = UeHomeRuntime(
        hass=hass,
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        device_passwords=dict(entry.data.get(CONF_DEVICE_PASSWORDS, {})),
        selected_serial_numbers=set(entry.data.get(CONF_DEVICES, [])),
    )
    await runtime.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload UeHome."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: UeHomeRuntime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.async_stop()

    return unload_ok
