"""UDP listener and state store for UeHome thermostats."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import socket
import time

from homeassistant.core import HomeAssistant, callback

from .const import DEFAULT_PORT
from .protocol import UeHomePacketError, UeHomeState, build_set_payload, parse_state_packet

_LOGGER = logging.getLogger(__name__)

StateListener = Callable[[str], None]


@dataclass
class UeHomeRuntime:
    """Runtime state shared by UeHome platforms."""

    hass: HomeAssistant
    port: int = DEFAULT_PORT
    device_passwords: dict[str, str] = field(default_factory=dict)
    selected_serial_numbers: set[str] = field(default_factory=set)
    states: dict[str, UeHomeState] = field(default_factory=dict)
    hosts: dict[str, str] = field(default_factory=dict)
    discovered_hosts: dict[str, str] = field(default_factory=dict)
    _listeners: list[StateListener] = field(default_factory=list)
    _transport: asyncio.DatagramTransport | None = None

    async def async_start(self) -> None:
        """Start the read-only UDP state listener."""

        if self._transport is not None:
            return

        loop = asyncio.get_running_loop()
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: _UeHomeDatagramProtocol(self),
            local_addr=("0.0.0.0", self.port),
            allow_broadcast=True,
        )
        self._transport = transport
        _LOGGER.info("Listening for UeHome state broadcasts on UDP %s", self.port)

    async def async_stop(self) -> None:
        """Stop the UDP listener."""

        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @callback
    def async_subscribe(self, listener: StateListener) -> Callable[[], None]:
        """Subscribe to state updates. The listener receives a serial number."""

        self._listeners.append(listener)

        @callback
        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    @callback
    def async_set_state(self, state: UeHomeState, host: str) -> None:
        """Store a decoded state packet and notify platforms."""

        self.discovered_hosts[state.serial_number] = host

        if (
            self.selected_serial_numbers
            and state.serial_number not in self.selected_serial_numbers
        ):
            return

        self.states[state.serial_number] = state
        self.hosts[state.serial_number] = host
        for listener in list(self._listeners):
            listener(state.serial_number)

    async def async_send_values(
        self,
        serial_number: str,
        values: dict[str, object],
    ) -> None:
        """Send a minimal control command to the last-seen device host."""

        host = self.hosts.get(serial_number)
        if host is None:
            raise UeHomePacketError(f"no known host for {serial_number}")

        payload = build_set_payload(
            serial_number=serial_number,
            values=values,
            password=self.device_passwords.get(serial_number),
        )
        _LOGGER.debug(
            "Sending UeHome command to %s:%s: %s",
            host,
            self.port,
            payload.decode("utf-8"),
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _send_udp, payload, host, self.port)


class _UeHomeDatagramProtocol(asyncio.DatagramProtocol):
    """Read-only asyncio datagram protocol for UeHome broadcasts."""

    def __init__(self, runtime: UeHomeRuntime) -> None:
        self._runtime = runtime

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Decode a broadcast packet and update Home Assistant state."""

        try:
            state = parse_state_packet(data)
        except UeHomePacketError as err:
            _LOGGER.debug("Ignoring non-UeHome UDP packet from %s: %s", addr, err)
            return

        self._runtime.hass.loop.call_soon_threadsafe(
            self._runtime.async_set_state,
            state,
            addr[0],
        )

    def error_received(self, exc: Exception) -> None:
        """Log UDP listener errors."""

        _LOGGER.warning("UeHome UDP listener error: %s", exc)


def _send_udp(payload: bytes, host: str, port: int) -> None:
    """Send one UDP command packet."""

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(payload, (host, port))


async def async_discover_devices(
    port: int = DEFAULT_PORT,
    timeout: int = 10,
) -> dict[str, str]:
    """Discover UeHome devices by passively listening for UDP state packets."""

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _discover_devices, port, timeout)


def _discover_devices(port: int, timeout: int) -> dict[str, str]:
    """Blocking UDP discovery helper."""

    devices: dict[str, str] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", port))
        sock.settimeout(0.5)
        deadline = time.monotonic() + timeout

        while True:
            if time.monotonic() >= deadline:
                break
            try:
                payload, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue

            try:
                state = parse_state_packet(payload)
            except UeHomePacketError:
                continue

            devices[state.serial_number] = addr[0]

    return devices
