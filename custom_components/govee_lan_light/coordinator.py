"""DataUpdateCoordinator for Govee LAN Light."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import GoveeDeviceState, GoveeLanApi
from .const import DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class GoveeLanLightCoordinator(DataUpdateCoordinator[GoveeDeviceState | None]):
    """Coordinator for polling Govee device state.

    Some Govee devices (like H607C) don't respond to status queries,
    so we track state locally and assume device is available.
    """

    def __init__(self, hass: HomeAssistant, api: GoveeLanApi, name: str) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance.
            api: GoveeLanApi instance for the device.
            name: Name of the device for logging.
        """
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.api = api
        self._available = True
        # Track state locally for devices that don't respond to status queries
        self._local_state = GoveeDeviceState(
            on=False,
            brightness=100,
            color=(255, 255, 255),
            color_temp_kelvin=0,
        )
        self._supports_status_query = True

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def local_state(self) -> GoveeDeviceState:
        """Return the locally tracked state."""
        return self._local_state

    def update_local_state(
        self,
        on: bool | None = None,
        brightness: int | None = None,
        color: tuple[int, int, int] | None = None,
        color_temp_kelvin: int | None = None,
    ) -> None:
        """Update the locally tracked state.

        Args:
            on: New on/off state.
            brightness: New brightness (1-100).
            color: New RGB color tuple.
            color_temp_kelvin: New color temperature in Kelvin.
        """
        if on is not None:
            self._local_state.on = on
        if brightness is not None:
            self._local_state.brightness = brightness
        if color is not None:
            self._local_state.color = color
            self._local_state.color_temp_kelvin = 0
        if color_temp_kelvin is not None:
            self._local_state.color_temp_kelvin = color_temp_kelvin
            self._local_state.color = (0, 0, 0)

    async def _async_update_data(self) -> GoveeDeviceState | None:
        """Fetch data from the device.

        Returns:
            GoveeDeviceState if device responds, or local state if device
            doesn't support status queries.
        """
        # If we already know device doesn't support status queries, skip
        if not self._supports_status_query:
            self._available = True
            return self._local_state

        try:
            state = await self.api.get_device_state()

            if state is None:
                # Device didn't respond - might not support status queries
                # Mark as not supporting and use local state
                _LOGGER.debug(
                    "Device %s did not respond to status query, using local state tracking",
                    self.api.host,
                )
                self._supports_status_query = False
                self._available = True
                return self._local_state

            self._available = True
            # Update local state with actual device state
            self._local_state = state
            return state

        except Exception as err:
            _LOGGER.debug("Error updating %s: %s", self.api.host, err)
            # Still consider available if we're using local state
            self._available = True
            return self._local_state

    async def async_refresh_immediate(self) -> None:
        """Request an immediate refresh of the device state."""
        # For devices that don't support status queries, just notify listeners
        if not self._supports_status_query:
            self.async_set_updated_data(self._local_state)
        else:
            await self.async_request_refresh()
