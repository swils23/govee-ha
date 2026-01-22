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
    """Coordinator for polling Govee device state."""

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

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.last_update_success

    async def _async_update_data(self) -> GoveeDeviceState | None:
        """Fetch data from the device.

        Returns:
            GoveeDeviceState if successful.

        Raises:
            UpdateFailed: If unable to communicate with device.
        """
        state = await self.api.get_device_state()

        if state is None:
            raise UpdateFailed(f"Unable to get state from {self.api.host}")

        return state
