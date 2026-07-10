"""Climate entities for UeHome floor-heating thermostats."""

from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .const import ATTR_SERIAL_NUMBER, DOMAIN
from .coordinator import UeHomeRuntime
from .entity import UeHomeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up UeHome climate entities."""

    runtime: UeHomeRuntime = hass.data[DOMAIN][entry.entry_id]
    known: set[str] = set()

    def add_missing(serial_number: str) -> None:
        if serial_number in known:
            return
        known.add(serial_number)
        async_add_entities([UeHomeClimate(runtime, serial_number)])

    for serial_number in runtime.states:
        add_missing(serial_number)

    entry.async_on_unload(runtime.async_subscribe(add_missing))


class UeHomeClimate(UeHomeEntity, ClimateEntity):
    """Climate entity for a UeHome thermostat."""

    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1

    def __init__(self, runtime: UeHomeRuntime, serial_number: str) -> None:
        super().__init__(runtime, serial_number)
        self._attr_unique_id = f"{serial_number}_climate"
        self._attr_name = None

    @property
    def current_temperature(self) -> float | None:
        state = self.uehome_state
        return state.current_temperature if state else None

    @property
    def target_temperature(self) -> float | None:
        state = self.uehome_state
        return state.target_temperature if state else None

    @property
    def hvac_mode(self) -> HVACMode | None:
        state = self.uehome_state
        if state is None or state.is_closed is None:
            return None
        return HVACMode.OFF if state.is_closed else HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        state = self.uehome_state
        if state is None:
            return None
        if state.is_closed is True:
            return HVACAction.OFF
        if state.is_heating is True:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, int | str | None]:
        return {ATTR_SERIAL_NUMBER: self._serial_number}

    async def async_set_temperature(self, **kwargs: object) -> None:
        """Set the heating target temperature."""

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self._runtime.async_send_values(
            self._serial_number,
            {"hw_temp_set": int(float(temperature))},
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the thermostat on or off."""

        if hvac_mode == HVACMode.OFF:
            close = True
        elif hvac_mode == HVACMode.HEAT:
            close = False
        else:
            return

        await self._runtime.async_send_values(
            self._serial_number,
            {"k_close": close},
        )
