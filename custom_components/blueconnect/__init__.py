from __future__ import annotations

import asyncio
import logging

from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "blueconnect"

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.states.async_set("blueconnect.test_state", 42)
    _LOGGER.info("blueconnect loaded")
    return True