"""Config flow for Govee LAN Light integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .api import discover_devices
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME, default="Govee Light"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.

    Note: Many Govee devices (like H607C) don't respond to status queries,
    so we just validate the IP format and trust the user. Control commands
    will work even without status query support.
    """
    import ipaddress

    host = data[CONF_HOST].strip()

    # Validate IP address format
    try:
        ipaddress.ip_address(host)
    except ValueError:
        raise CannotConnect

    return {
        "title": data.get(CONF_NAME, f"Govee Light ({host})"),
        "host": host,
    }


class GoveeLanLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Govee LAN Light."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: list[dict[str, Any]] = []
        self._selected_device: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - attempt discovery first."""
        if user_input is None:
            # Try discovery first
            _LOGGER.debug("Starting device discovery")
            discovered = await discover_devices()

            if discovered:
                # Found devices via discovery
                self._discovered_devices = [
                    {
                        "host": device.ip,
                        "name": f"{device.sku} ({device.ip})" if device.sku else device.ip,
                        "device_id": device.device,
                        "mac": device.mac,
                        "sku": device.sku,
                    }
                    for device in discovered
                ]
                return await self.async_step_select_device()

            # No devices found - show manual entry form
            _LOGGER.debug("No devices discovered, showing manual entry form")
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "message": "No devices were automatically discovered. Please enter the IP address manually."
                },
            )

        # User submitted manual entry form
        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Use host as unique_id for manually added devices
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_HOST: info["host"],
                    CONF_NAME: user_input.get(CONF_NAME, info["title"]),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle device selection from discovered devices."""
        if user_input is not None:
            selected_host = user_input["device"]

            if selected_host == "manual":
                return await self.async_step_manual()

            # Find the selected device
            for device in self._discovered_devices:
                if device["host"] == selected_host:
                    self._selected_device = device
                    break

            if self._selected_device:
                # Set unique_id based on device_id or MAC if available
                unique_id = (
                    self._selected_device.get("mac")
                    or self._selected_device.get("device_id")
                    or self._selected_device["host"]
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._selected_device["name"],
                    data={
                        CONF_HOST: self._selected_device["host"],
                        CONF_NAME: self._selected_device["name"],
                        "device_id": self._selected_device.get("device_id"),
                        "mac": self._selected_device.get("mac"),
                        "sku": self._selected_device.get("sku"),
                    },
                )

        # Build device selection options
        device_options = {
            device["host"]: device["name"] for device in self._discovered_devices
        }
        device_options["manual"] = "Enter IP address manually"

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual IP entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=info["title"],
                data={
                    CONF_HOST: info["host"],
                    CONF_NAME: user_input.get(CONF_NAME, info["title"]),
                },
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
