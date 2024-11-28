"""Blueconnect Go integration.

Todo:
 - Use async_config_entry
 - Use config flow to find the device

"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.core_config import Config
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from functools import partial

DOMAIN = "blueconnect"
BT_ADDRESS = "bluetooth_address"
PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

# send true 0x01 to this service ID
blueriiot_send_service_uuid = "F3300001-F0A2-9B06-0C59-1BC4763B5C00"
blueriiot_send_characteristic_uuid = "F3300002-F0A2-9B06-0C59-1BC4763B5C00"

# notification is received on this Service ID
blueriiot_receive_service_uuid = "F3300001-F0A2-9B06-0C59-1BC4763B5C00"
blueriiot_receive_characteristic_uuid = "F3300003-F0A2-9B06-0C59-1BC4763B5C00"


def _async_mynew(
    hass: HomeAssistant,
    service_info: bluetooth.BluetoothServiceInfoBleak,
    change: bluetooth.BluetoothChange,
) -> None:
    _LOGGER.info(f"New device --> {service_info}.")  # noqa: G004


def _on_data(char_specifier, data: bytearray):
    _LOGGER.info(f" --> data: {data}")  # noqa: G004


# async def _read_data(ble_device: BLEDevice):
async def _read_data(hass: HomeAssistant, bt_address: str):
    _LOGGER.info("Reading data")
    ble_device = bluetooth.async_ble_device_from_address(hass, bt_address)
    if ble_device is None:
        _LOGGER.error("Blueconnect device not found")
        return

    client = await establish_connection(BleakClient, ble_device, ble_device.address)

    # data = await client.read_gatt_char(blueriiot_receive_characteristic_uuid)
    # _LOGGER.info(f" --> data: {data}")  # noqa: G004

    await client.start_notify(blueriiot_receive_characteristic_uuid, _on_data)
    _LOGGER.info("Set to notify")

    await client.write_gatt_char(
        blueriiot_send_characteristic_uuid, b"\x01", response=True
    )
    _LOGGER.info("Wrote the thing")

    # Sleep for 10 seconds
    await asyncio.sleep(20)

    _LOGGER.info("Disconnecting")
    await client.disconnect()


async def _dummy():
    _LOGGER.info("Dummy")


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Async setup."""
    hass.data.setdefault(DOMAIN, {})
    # hass.states.async_set("blueconnect.test_state", 42)

    bt_address = config.get(DOMAIN, {}).get(BT_ADDRESS)
    _LOGGER.info(f"Confgured address: {bt_address}.")  # noqa: G004
    # bluetooth.async_register_callback(
    #     hass,
    #     partial(_async_mynew, hass),
    #     {"address": bt_address},
    #     bluetooth.BluetoothScanningMode.ACTIVE,
    # )

    ble_device = bluetooth.async_ble_device_from_address(hass, bt_address)
    if ble_device is None:
        _LOGGER.error("Blueconnect device not found")
    else:
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=DOMAIN,
            # update_method=partial(_read_data, hass, bt_address),
            update_method=_dummy,
            update_interval=timedelta(seconds=10),
        )
        _LOGGER.info("Setting up coordinator")
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN] = {
            "coordinator": coordinator,
        }

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
