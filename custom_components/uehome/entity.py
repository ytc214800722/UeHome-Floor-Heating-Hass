"""Shared entity helpers for UeHome."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, MANUFACTURER
from .coordinator import UeHomeRuntime
from .protocol import UeHomeState


class UeHomeEntity(Entity):
    """Base class for UeHome entities."""

    _attr_has_entity_name = True

    def __init__(self, runtime: UeHomeRuntime, serial_number: str) -> None:
        self._runtime = runtime
        self._serial_number = serial_number

    @property
    def uehome_state(self) -> UeHomeState | None:
        """Return the latest decoded device state."""

        return self._runtime.states.get(self._serial_number)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device metadata."""

        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            manufacturer=MANUFACTURER,
            name=f"UeHome {self._serial_number}",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe entity to push updates."""

        self.async_on_remove(self._runtime.async_subscribe(self._handle_update))

    def _handle_update(self, serial_number: str) -> None:
        if serial_number == self._serial_number:
            self.async_write_ha_state()
