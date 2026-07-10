"""Protocol helpers for UeHome UDP state packets."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

try:
    from .const import DEFAULT_SEQUENCE, DEFAULT_VERSION
except ImportError:
    DEFAULT_SEQUENCE = 3
    DEFAULT_VERSION = 1


class UeHomePacketError(ValueError):
    """Raised when a datagram does not contain a usable UeHome state packet."""


@dataclass(frozen=True)
class UeHomeState:
    """Read-only thermostat state decoded from a UeHome UDP broadcast."""

    serial_number: str
    raw: dict[str, Any]

    @property
    def is_closed(self) -> bool | None:
        return _as_bool(self.raw.get("k_close"))

    @property
    def current_temperature(self) -> float | None:
        return _as_float(self.raw.get("temp"))

    @property
    def target_temperature(self) -> float | None:
        return _as_float(self.raw.get("hw_temp_set"))

    @property
    def is_heating(self) -> bool | None:
        return _as_bool(self.raw.get("is_heat"))


def parse_state_packet(packet: bytes) -> UeHomeState:
    """Parse a UeHome UDP datagram into a read-only state object.

    Observed packets contain a binary prefix, a UTF-8 JSON object, and a
    trailing NUL byte. The parser extracts the JSON object without assuming a
    fixed binary prefix length.
    """

    start = packet.find(b"{")
    end = packet.rfind(b"}")
    if start < 0 or end < start:
        raise UeHomePacketError("packet does not contain a JSON object")

    try:
        payload = packet[start : end + 1].decode("utf-8")
    except UnicodeDecodeError as err:
        raise UeHomePacketError("packet JSON is not valid UTF-8") from err

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as err:
        raise UeHomePacketError("packet JSON is invalid") from err

    if not isinstance(data, dict):
        raise UeHomePacketError("packet JSON is not an object")

    serial_number = data.get("sn")
    if serial_number is None:
        raise UeHomePacketError("packet JSON has no serial number")

    return UeHomeState(serial_number=str(serial_number), raw=data)


def build_set_payload(
    serial_number: str,
    values: dict[str, Any],
    password: str | None,
    sequence: int = DEFAULT_SEQUENCE,
    version: int = DEFAULT_VERSION,
) -> bytes:
    """Build the validated UeHome UDP control payload."""

    command = {
        **values,
        "seq": sequence,
        "version": version,
    }
    if password:
        command["p_w"] = password

    payload = ["", serial_number, "set", command]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
