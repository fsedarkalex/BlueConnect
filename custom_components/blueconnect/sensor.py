"""Blueconnect GO sensor platform."""

import logging
from datetime import timedelta
import random
from typing import Any, Callable, Dict, Optional

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ADDRESS,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

# Time between updating data from GitHub
SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.info("async_setup_platform")
    sensors = [BlueConnectGo(config[CONF_ADDRESS])]
    async_add_entities(sensors, update_before_add=True)


class BlueConnectGo(Entity):
    """Representation of a GitHub Repo sensor."""

    def __init__(self, address: str):
        super().__init__()
        self._address = address
        self._temperature = None
        self.force_update = True
        self.current_temperature = random.randint(0, 100)

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "Blue Connect Go"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return self._address

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return "on"

    @property
    def available(self) -> bool:
        return True

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "temperature": self.current_temperature,
        }

    async def async_update(self):
        _LOGGER.info("async_update")
        self.current_temperature = random.randint(0, 100)
        _LOGGER.info(f"Temperature now is {self.current_temperature}")
