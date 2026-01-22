"""The Govee LAN Light integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant

from .api import GoveeLanApi
from .const import DOMAIN
from .coordinator import GoveeLanLightCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee LAN Light from a config entry."""
    host = entry.data[CONF_HOST]
    name = entry.data.get(CONF_NAME, f"Govee Light ({host})")

    _LOGGER.debug("Setting up Govee LAN Light at %s", host)

    api = GoveeLanApi(host)
    coordinator = GoveeLanLightCoordinator(hass, api, name)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
