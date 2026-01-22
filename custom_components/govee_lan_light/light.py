"""Light entity for Govee LAN Light integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_BRIGHTNESS_GOVEE,
    MAX_COLOR_TEMP_KELVIN,
    MIN_BRIGHTNESS_GOVEE,
    MIN_COLOR_TEMP_KELVIN,
)
from .coordinator import GoveeLanLightCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Govee LAN Light from a config entry."""
    coordinator: GoveeLanLightCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([GoveeLanLight(coordinator, entry)])


class GoveeLanLight(CoordinatorEntity[GoveeLanLightCoordinator], LightEntity):
    """Representation of a Govee LAN Light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
    _attr_min_color_temp_kelvin = MIN_COLOR_TEMP_KELVIN
    _attr_max_color_temp_kelvin = MAX_COLOR_TEMP_KELVIN

    def __init__(
        self,
        coordinator: GoveeLanLightCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the light entity.

        Args:
            coordinator: The data update coordinator.
            entry: The config entry.
        """
        super().__init__(coordinator)
        self._entry = entry
        self._host = entry.data[CONF_HOST]
        self._attr_unique_id = entry.entry_id

        # Device info for device registry
        device_id = entry.data.get("device_id", self._host)
        sku = entry.data.get("sku", "Govee Light")
        mac = entry.data.get("mac")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=entry.data.get(CONF_NAME, f"Govee Light ({self._host})"),
            manufacturer="Govee",
            model=sku,
            sw_version=None,
        )
        if mac:
            self._attr_device_info["connections"] = {("mac", mac)}

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.on

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        if self.coordinator.data is None:
            return None
        # Convert Govee brightness (1-100) to HA brightness (0-255)
        govee_brightness = self.coordinator.data.brightness
        return round((govee_brightness / MAX_BRIGHTNESS_GOVEE) * 255)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        if self.coordinator.data is None:
            return None
        kelvin = self.coordinator.data.color_temp_kelvin
        # Return None if device is in RGB mode (kelvin = 0)
        if kelvin == 0:
            return None
        return kelvin

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the color mode of the light."""
        if self.coordinator.data is None:
            return None
        # If color temp is set (non-zero), we're in color temp mode
        if self.coordinator.data.color_temp_kelvin > 0:
            return ColorMode.COLOR_TEMP
        return ColorMode.RGB

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        api = self.coordinator.api

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert HA brightness (0-255) to Govee brightness (1-100)
            govee_brightness = max(
                MIN_BRIGHTNESS_GOVEE,
                min(
                    MAX_BRIGHTNESS_GOVEE,
                    round((ha_brightness / 255) * MAX_BRIGHTNESS_GOVEE),
                ),
            )
            await api.set_brightness(govee_brightness)

        # Handle RGB color
        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            await api.set_color(r, g, b)

        # Handle color temperature
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            await api.set_color_temp(kelvin)

        # Always turn on if no other attributes specified or in addition to them
        if not any(
            attr in kwargs
            for attr in [ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_COLOR_TEMP_KELVIN]
        ):
            await api.turn_on()
        elif not self.is_on:
            await api.turn_on()

        # Refresh state from device
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.api.turn_off()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
