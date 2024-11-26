"""Blueconnect Go integration.

Todo:
 - Use async_config_entry
 - Use config flow to find the device

"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config

DOMAIN = "blueconnect"
BT_ADDRESS = "bluetooth_address"
PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Async setup."""
    hass.data.setdefault(DOMAIN, {})
    # hass.states.async_set("blueconnect.test_state", 42)
    bt_address = config.get(DOMAIN, {}).get(BT_ADDRESS)
    _LOGGER.info(f"Confgured address: {bt_address}.")  # noqa: G004
    _LOGGER.info("Module blueconnect loaded")
    return bt_address is not None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup entry."""
    _LOGGER.info(f"Module blueconnect entry loaded: {entry}.")  # noqa: G004
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
