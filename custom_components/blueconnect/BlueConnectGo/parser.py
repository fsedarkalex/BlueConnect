"""Parser for BlueConnect Go BLE devices"""

from __future__ import annotations

from threading import Event
from functools import partial
import random
import asyncio
import dataclasses
import struct
from collections import namedtuple
from datetime import datetime
import logging

# from logging import Logger
from math import exp
from typing import Any, Callable, Tuple

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import BATT_100, BATT_0


READ_CHAR_UUID = "F3300003-F0A2-9B06-0C59-1BC4763B5C00"
BUTTON_CHAR_UUID = "F3300002-F0A2-9B06-0C59-1BC4763B5C00"

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BlueConnectGoDevice:
    """Response data with information about the Blue Connect Go device"""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )


# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class BlueConnectGoBluetoothDeviceData:
    """Data for Blue Connect Go BLE sensors."""

    _event: asyncio.Event | None
    _command_data: bytearray | None

    def __init__(
        self,
        logger: Logger,
    ):
        super().__init__()
        self.logger = logger
        self.logger.debug("In Device Data")

    async def _get_status(
        self, client: BleakClient, device: BlueConnectGoDevice
    ) -> BlueConnectGoDevice:
        _LOGGER.info("Getting Status")

        data_ready_event = Event()

        await client.start_notify(
            READ_CHAR_UUID, partial(self._receive_status, device, data_ready_event)
        )
        await client.write_gatt_char(BUTTON_CHAR_UUID, b"\x01", response=True)
        _LOGGER.info("Write sent")

        # try:
        #     await asyncio.wait_for(data_ready_event.wait(), timeout=20)
        # except TimeoutError:
        #     _LOGGER.warning("Timer expired")
        await asyncio.sleep(15)

        _LOGGER.info("Status acquisition finished")
        return device

    async def _receive_status(
        self,
        device: BlueConnectGoDevice,
        data_ready_event: Event,
        char_specifier: str,
        data: bytearray,
    ) -> None:
        _LOGGER.info("Got new data")
        data_ready_event.set()

        _LOGGER.info(
            f"  -> frame array hex: {":".join([f"{byte:02X}" for byte in data])}"  # noqa: G004
        )

        raw_temp = int.from_bytes(data[1:3], byteorder="little")
        device.sensors["temperature"] = raw_temp / 100.0

        raw_ph = int.from_bytes(data[3:5], byteorder="little")
        device.sensors["pH"] = (2048 - raw_ph) / 232.0 + 7.0

        raw_orp = int.from_bytes(data[5:7], byteorder="little")
        device.sensors["ORP"] = raw_orp / 3.86 - 21.57826

        raw_salt = int.from_bytes(data[7:9], byteorder="little")
        device.sensors["salt"] = raw_salt / 25.0

        raw_cond = int.from_bytes(data[9:11], byteorder="little")
        device.sensors["EC"] = raw_cond / 0.4134

        raw_batt = int(data[11])
        device.sensors["battery"] = raw_batt

        _LOGGER.debug("Got Status")
        return device

    async def update_device(
        self, ble_device: BLEDevice, skip_query=False
    ) -> BlueConnectGoDevice:
        """Connects to the device through BLE and retrieves relevant data"""
        _LOGGER.debug("Update Device")

        device = BlueConnectGoDevice()
        device.name = ble_device.address
        device.address = ble_device.address
        _LOGGER.debug("device.name: %s", device.name)
        _LOGGER.debug("device.address: %s", device.address)

        if not skip_query:
            client = await establish_connection(
                BleakClient, ble_device, ble_device.address
            )
            _LOGGER.debug("Got Client")
            await self._get_status(client, device)
            _LOGGER.debug("got Status")
            await client.disconnect()

        return device
