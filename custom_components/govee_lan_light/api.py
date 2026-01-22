"""UDP API implementation for Govee LAN Light."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from dataclasses import dataclass
from typing import Any

from .const import (
    MAX_RETRIES,
    MULTICAST_ADDRESS,
    PORT_CONTROL,
    PORT_LISTEN,
    PORT_SCAN,
    TIMEOUT_COMMAND,
    TIMEOUT_DISCOVERY,
    TIMEOUT_STATUS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class GoveeDeviceState:
    """Represents the current state of a Govee device."""

    on: bool = False
    brightness: int = 100
    color: tuple[int, int, int] = (255, 255, 255)
    color_temp_kelvin: int = 0


@dataclass
class GoveeDeviceInfo:
    """Represents discovered device information."""

    ip: str
    device: str
    sku: str
    mac: str | None = None


class GoveeLanApi:
    """API for communicating with Govee devices over LAN."""

    def __init__(self, host: str) -> None:
        """Initialize the API.

        Args:
            host: IP address of the Govee device.
        """
        self._host = host
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        """Return the host IP address."""
        return self._host

    async def _send_udp_command(
        self,
        message: dict[str, Any],
        port: int,
        timeout: float,
        expect_response: bool = True,
    ) -> dict[str, Any] | None:
        """Send a UDP command and optionally wait for response.

        Args:
            message: Command message to send.
            port: UDP port to send to.
            timeout: Timeout in seconds.
            expect_response: Whether to wait for a response.

        Returns:
            Response dict or None if no response expected/received.
        """
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            data = json.dumps(message).encode("utf-8")
            _LOGGER.debug("Sending to %s:%d: %s", self._host, port, message)
            await loop.sock_sendto(sock, data, (self._host, port))

            if not expect_response:
                return None

            sock.settimeout(timeout)
            try:
                response_data, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 4096),
                    timeout=timeout,
                )
                response = json.loads(response_data.decode("utf-8"))
                _LOGGER.debug("Received from %s: %s", self._host, response)
                return response
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout waiting for response from %s", self._host)
                return None
        except OSError as err:
            _LOGGER.error("Socket error communicating with %s: %s", self._host, err)
            return None
        finally:
            sock.close()

    async def get_device_state(self) -> GoveeDeviceState | None:
        """Query the device for its current state.

        The device responds on port 4002, not on the sending socket,
        so we need to bind to 4002 before sending the query to 4003.

        Returns:
            GoveeDeviceState if successful, None otherwise.
        """
        message = {"msg": {"cmd": "devStatus", "data": {}}}

        for attempt in range(MAX_RETRIES):
            async with self._lock:
                response = await self._send_status_query(
                    message,
                    TIMEOUT_STATUS * (attempt + 1),
                )

            if response and "msg" in response:
                msg = response["msg"]
                if msg.get("cmd") == "devStatus" and "data" in msg:
                    data = msg["data"]
                    return GoveeDeviceState(
                        on=data.get("onOff") == 1,
                        brightness=data.get("brightness", 100),
                        color=(
                            data.get("color", {}).get("r", 255),
                            data.get("color", {}).get("g", 255),
                            data.get("color", {}).get("b", 255),
                        ),
                        color_temp_kelvin=data.get("colorTemInKelvin", 0),
                    )

            _LOGGER.debug(
                "Attempt %d/%d failed to get state from %s",
                attempt + 1,
                MAX_RETRIES,
                self._host,
            )

        return None

    async def _send_status_query(
        self,
        message: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any] | None:
        """Send a status query and wait for response on port 4002.

        Govee devices respond to status queries on port 4002, not on the
        sending socket. We bind to 4002, send query to 4003, then receive.

        Args:
            message: Status query message.
            timeout: Timeout in seconds.

        Returns:
            Response dict or None if no response received.
        """
        loop = asyncio.get_event_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            # Bind to port 4002 to receive responses
            sock.bind(("", PORT_LISTEN))
        except OSError as err:
            _LOGGER.debug("Failed to bind to port %d: %s", PORT_LISTEN, err)
            sock.close()
            return None

        try:
            data = json.dumps(message).encode("utf-8")
            _LOGGER.debug("Sending status query to %s:%d: %s", self._host, PORT_CONTROL, message)
            await loop.sock_sendto(sock, data, (self._host, PORT_CONTROL))

            try:
                response_data, addr = await asyncio.wait_for(
                    loop.sock_recvfrom(sock, 4096),
                    timeout=timeout,
                )
                # Only accept responses from our target device
                if addr[0] == self._host:
                    response = json.loads(response_data.decode("utf-8"))
                    _LOGGER.debug("Received status from %s: %s", self._host, response)
                    return response
                else:
                    _LOGGER.debug("Ignoring response from %s (expected %s)", addr[0], self._host)
                    return None
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout waiting for status response from %s", self._host)
                return None
        except OSError as err:
            _LOGGER.error("Socket error querying status from %s: %s", self._host, err)
            return None
        finally:
            sock.close()

    async def turn_on(self) -> bool:
        """Turn on the device.

        Returns:
            True if command was sent successfully.
        """
        message = {"msg": {"cmd": "turn", "data": {"value": 1}}}
        async with self._lock:
            await self._send_udp_command(
                message, PORT_CONTROL, TIMEOUT_COMMAND, expect_response=False
            )
        return True

    async def turn_off(self) -> bool:
        """Turn off the device.

        Returns:
            True if command was sent successfully.
        """
        message = {"msg": {"cmd": "turn", "data": {"value": 0}}}
        async with self._lock:
            await self._send_udp_command(
                message, PORT_CONTROL, TIMEOUT_COMMAND, expect_response=False
            )
        return True

    async def set_brightness(self, brightness: int) -> bool:
        """Set the brightness level.

        Args:
            brightness: Brightness value (1-100).

        Returns:
            True if command was sent successfully.
        """
        brightness = max(1, min(100, brightness))
        message = {"msg": {"cmd": "brightness", "data": {"value": brightness}}}
        async with self._lock:
            await self._send_udp_command(
                message, PORT_CONTROL, TIMEOUT_COMMAND, expect_response=False
            )
        return True

    async def set_color(self, r: int, g: int, b: int) -> bool:
        """Set the RGB color.

        Args:
            r: Red value (0-255).
            g: Green value (0-255).
            b: Blue value (0-255).

        Returns:
            True if command was sent successfully.
        """
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        message = {
            "msg": {
                "cmd": "colorwc",
                "data": {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0},
            }
        }
        async with self._lock:
            await self._send_udp_command(
                message, PORT_CONTROL, TIMEOUT_COMMAND, expect_response=False
            )
        return True

    async def set_color_temp(self, kelvin: int) -> bool:
        """Set the color temperature.

        Args:
            kelvin: Color temperature in Kelvin (2000-9000).

        Returns:
            True if command was sent successfully.
        """
        kelvin = max(2000, min(9000, kelvin))
        message = {
            "msg": {
                "cmd": "colorwc",
                "data": {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": kelvin},
            }
        }
        async with self._lock:
            await self._send_udp_command(
                message, PORT_CONTROL, TIMEOUT_COMMAND, expect_response=False
            )
        return True

    async def check_connection(self) -> bool:
        """Check if the device is reachable.

        Returns:
            True if device responds to status query.
        """
        state = await self.get_device_state()
        return state is not None


async def discover_devices(timeout: float = TIMEOUT_DISCOVERY) -> list[GoveeDeviceInfo]:
    """Discover Govee devices on the network using UDP multicast.

    This implementation includes a fallback to use the sender's IP address
    when the device doesn't include an 'ip' field in its response (common
    with H60xx floor lamps).

    Args:
        timeout: Discovery timeout in seconds.

    Returns:
        List of discovered GoveeDeviceInfo objects.
    """
    devices: list[GoveeDeviceInfo] = []
    loop = asyncio.get_event_loop()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setblocking(False)

    try:
        sock.bind(("", PORT_LISTEN))
    except OSError as err:
        _LOGGER.error("Failed to bind to port %d: %s", PORT_LISTEN, err)
        sock.close()
        return devices

    scan_message = {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}
    data = json.dumps(scan_message).encode("utf-8")

    try:
        await loop.sock_sendto(sock, data, (MULTICAST_ADDRESS, PORT_SCAN))
        _LOGGER.debug("Sent discovery message to %s:%d", MULTICAST_ADDRESS, PORT_SCAN)
    except OSError as err:
        _LOGGER.error("Failed to send discovery message: %s", err)
        sock.close()
        return devices

    end_time = loop.time() + timeout
    seen_devices: set[str] = set()

    while loop.time() < end_time:
        try:
            remaining = end_time - loop.time()
            if remaining <= 0:
                break

            response_data, sender_addr = await asyncio.wait_for(
                loop.sock_recvfrom(sock, 4096),
                timeout=remaining,
            )
            sender_ip = sender_addr[0]

            try:
                response = json.loads(response_data.decode("utf-8"))
                _LOGGER.debug("Discovery response from %s: %s", sender_ip, response)

                if "msg" in response:
                    msg = response["msg"]
                    if msg.get("cmd") == "scan" and "data" in msg:
                        device_data = msg["data"]

                        # Critical: Use sender IP as fallback if 'ip' field is missing
                        # This is common with H60xx floor lamps
                        device_ip = device_data.get("ip") or sender_ip

                        device_id = device_data.get("device", "")

                        if device_id and device_id not in seen_devices:
                            seen_devices.add(device_id)
                            devices.append(
                                GoveeDeviceInfo(
                                    ip=device_ip,
                                    device=device_id,
                                    sku=device_data.get("sku", ""),
                                    mac=device_data.get("mac"),
                                )
                            )
                            _LOGGER.info(
                                "Discovered Govee device: %s (%s) at %s",
                                device_data.get("sku", "Unknown"),
                                device_id,
                                device_ip,
                            )

            except json.JSONDecodeError:
                _LOGGER.debug("Invalid JSON response from %s", sender_ip)

        except asyncio.TimeoutError:
            break
        except OSError as err:
            _LOGGER.debug("Socket error during discovery: %s", err)
            break

    sock.close()
    return devices
