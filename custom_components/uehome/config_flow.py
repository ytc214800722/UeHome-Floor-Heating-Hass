"""Config flow for the UeHome floor-heating integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_PASSWORDS,
    CONF_DEVICES,
    CONF_DISCOVERED_DEVICES,
    DEFAULT_PORT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from .coordinator import UeHomeRuntime, async_discover_devices


class UeHomeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for UeHome."""

    VERSION = 1

    def __init__(self) -> None:
        self._port = DEFAULT_PORT
        self._discovered: dict[str, str] = {}
        self._selected: list[str] = []

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Scan for devices before choosing which ones to add."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._port = user_input[CONF_PORT]
            try:
                self._discovered = await self._async_get_discovered_devices()
            except OSError:
                errors["base"] = "cannot_listen"
            else:
                configured = self._configured_serial_numbers()
                self._discovered = {
                    serial_number: host
                    for serial_number, host in self._discovered.items()
                    if serial_number not in configured
                }
                if not self._discovered:
                    errors["base"] = "no_new_devices"
                else:
                    return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PORT, default=self._port): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=1, max=65535),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_select(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Let the user choose which discovered devices to add."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._selected = list(user_input.get(CONF_DEVICES, []))
            if not self._selected:
                errors[CONF_DEVICES] = "no_devices_selected"
            else:
                return await self.async_step_passwords()

        options = [
            {
                "value": serial_number,
                "label": f"{serial_number} ({host})",
            }
            for serial_number, host in sorted(self._discovered.items())
        ]

        return self.async_show_form(
            step_id="select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_passwords(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Collect passwords for selected devices."""

        errors: dict[str, str] = {}

        if user_input is not None:
            passwords = {
                serial_number: user_input.get(_password_key(serial_number), "")
                for serial_number in self._selected
            }
            missing = [
                serial_number
                for serial_number, password in passwords.items()
                if not str(password).strip()
            ]
            if missing:
                errors["base"] = "password_required"
            else:
                return await self._async_save_selected_devices(passwords)

        schema = {
            vol.Required(_password_key(serial_number)): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            )
            for serial_number in self._selected
        }

        return self.async_show_form(
            step_id="passwords",
            data_schema=vol.Schema(schema),
            description_placeholders={
                CONF_DISCOVERED_DEVICES: ", ".join(self._selected),
            },
            errors=errors,
        )

    async def _async_save_selected_devices(
        self,
        passwords: dict[str, str],
    ) -> FlowResult:
        """Create or update the UeHome config entry."""

        current_entries = self._async_current_entries()
        if current_entries:
            entry = current_entries[0]
            devices = list(dict.fromkeys([*entry.data.get(CONF_DEVICES, []), *self._selected]))
            device_passwords = {
                **entry.data.get(CONF_DEVICE_PASSWORDS, {}),
                **passwords,
            }
            data = {
                **entry.data,
                CONF_PORT: entry.data.get(CONF_PORT, self._port),
                CONF_DEVICES: devices,
                CONF_DEVICE_PASSWORDS: device_passwords,
            }
            self.hass.config_entries.async_update_entry(entry, data=data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="devices_added")

        return self.async_create_entry(
            title="UeHome Floor Heating",
            data={
                CONF_PORT: self._port,
                CONF_DEVICES: self._selected,
                CONF_DEVICE_PASSWORDS: passwords,
            },
        )

    async def _async_get_discovered_devices(self) -> dict[str, str]:
        """Return discovered devices from the running listener or a short scan."""

        runtimes: dict[str, UeHomeRuntime] = self.hass.data.get(DOMAIN, {})
        discovered: dict[str, str] = {}
        for runtime in runtimes.values():
            if runtime.port == self._port:
                discovered.update(runtime.discovered_hosts)
                discovered.update(runtime.hosts)

        if discovered:
            return discovered

        return await async_discover_devices(
            port=self._port,
            timeout=DISCOVERY_TIMEOUT,
        )

    def _configured_serial_numbers(self) -> set[str]:
        """Return all serial numbers already configured."""

        configured: set[str] = set()
        for entry in self._async_current_entries():
            configured.update(entry.data.get(CONF_DEVICES, []))
        return configured


def _password_key(serial_number: str) -> str:
    """Return the form field key for a device password."""

    return f"{CONF_PASSWORD}_{serial_number}"
