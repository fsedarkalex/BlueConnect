"""Parser for BlueConnect Go BLE devices."""

from __future__ import annotations

import asyncio
from asyncio import Event
import dataclasses
from functools import partial
import logging
from logging import Logger

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from .const import BUTTON_CHAR_UUID, NOTIFY_CHAR_UUID, NOTIFY_TIMEOUT

import math

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class BlueConnectGoDevice:
    """Response data with information about the Blue Connect Go device."""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )
    chlorine_history: list[float] = dataclasses.field(default_factory=list)
    salt_history: list[float] = dataclasses.field(default_factory=list)

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
class BlueConnectGoBluetoothDeviceData:
    """Data for Blue Connect Go BLE sensors."""

    _event: asyncio.Event | None
    _command_data: bytearray | None

    def __init__(
        self,
        logger: Logger,
    ) -> None:
        """Initialize the class."""
        super().__init__()
        self.logger = logger
        self.logger.debug("In Device Data")
        self._max_history_len = 3 #for smoothing some mesaurements, double value taken for salt as it is a usually not changing value

    async def _get_status(
        self, client: BleakClient, device: BlueConnectGoDevice
    ) -> BlueConnectGoDevice:
        _LOGGER.debug("Getting Status")

        data_ready_event = Event()

        await client.start_notify(
            NOTIFY_CHAR_UUID, partial(self._receive_status, device, data_ready_event)
        )
        await client.write_gatt_char(BUTTON_CHAR_UUID, b"\x01", response=True)
        _LOGGER.debug("Write sent")

        try:
            await asyncio.wait_for(data_ready_event.wait(), timeout=NOTIFY_TIMEOUT)
        except TimeoutError:
            _LOGGER.warning("Timer expired")

        _LOGGER.debug("Status acquisition finished")
        return device

    async def _receive_status(
        self,
        device: BlueConnectGoDevice,
        data_ready_event: Event,
        char_specifier: str,
        data: bytearray,
    ) -> None:
        _LOGGER.debug("Got new data")
        data_ready_event.set()

        frame_hex = ":".join(f"{b:02X}" for b in data)
        _LOGGER.debug("  -> frame array hex: %s", frame_hex)

        # Temperature
        raw_temp = int.from_bytes(data[1:3], byteorder="little")
        _LOGGER.debug("raw_temp: %s", raw_temp)
        actual_temp = raw_temp / 100.0
        _LOGGER.debug("actual_temp: %s", actual_temp)
        device.sensors["temperature"] = actual_temp

        # pH
        PH_CENTER = 2048
        PH_SCALE = 232.0
        PH_OFFSET = 7.2
        raw_ph = int.from_bytes(data[3:5], byteorder="little")
        _LOGGER.debug("raw_ph: %s", raw_ph)
        actual_ph = (PH_CENTER - raw_ph) / PH_SCALE + PH_OFFSET
        _LOGGER.debug("actual_ph: %s", actual_ph)
        device.sensors["pH"] = actual_ph

        # ORP
        raw_orp = int.from_bytes(data[5:7], byteorder="little")
        _LOGGER.debug("raw_orp: %s", raw_orp)
        actual_orp = raw_orp / 4.0 - 5.0
        _LOGGER.debug("actual_orp: %s", actual_orp)
        device.sensors["ORP"] = actual_orp

        # Electrical Conductivity and Salt
        raw_ec = int.from_bytes(data[7:9], byteorder="little")
        _LOGGER.debug("raw_ec: %s µS/cm", raw_ec)

        if raw_ec != 0:
            # Empirical conversion based on BlueConnect output (≈0.226 ppm per µS/cm)
            EC_TO_PPM_NACL = 0.256  # BlueConnect appears to use this
            salt_ppm = raw_ec * EC_TO_PPM_NACL
            _LOGGER.debug(" - salt_ppm: %s", salt_ppm)
            
            device.sensors["salt_raw"] = round(salt_ppm, 1)

            # Smoothing history
            device.salt_history.append(salt_ppm)
            if len(device.salt_history) > self._max_history_len * 2:
                device.salt_history.pop(0)

            smooth_salt = sum(device.salt_history) / len(device.salt_history)
            device.sensors["salt"] = round(smooth_salt, 2)
            device.sensors["salt_grams"] = round(smooth_salt / 1000, 1)
            device.sensors["EC"] = raw_ec
            _LOGGER.debug(" - smoothed salt (g/l): %s", device.sensors["salt"])
        else:
            device.sensors["EC"] = None
            device.sensors["salt"] = None
            device.sensors["salt_raw"] = None
            device.sensors["salt_grams"] = None

        # Free chlorine
        try:
            _LOGGER.debug("calculating chlorine...")

            R = 8.314     # Gas constant J/(mol·K)
            F = 96485     # Faraday constant C/mol
            LOG10 = math.log(10)
            temp_K = actual_temp + 273.15
            _LOGGER.debug(" - temp_K: %s", temp_K)

            nernst_slope = (R * temp_K) / (F * LOG10) * 1000  # in mV
            _LOGGER.debug(" - nernst_slope (mV): %s", nernst_slope)

            # Base ORP reference for pH=7 (adjust if needed)
            orp_ref_base = 700  
            orp_ref = orp_ref_base - (actual_ph - 7.0) * nernst_slope
            orp_diff = actual_orp - orp_ref
            _LOGGER.debug(" - orp_ref: %s", orp_ref)
            _LOGGER.debug(" - orp_diff: %s", orp_diff)

            # Estimate log10 concentration of HOCl (mol/L)
            log_chlorine_mol = orp_diff / nernst_slope
            _LOGGER.debug(" - log_chlorine_mol: %s", log_chlorine_mol)

            # Clamp between -6 and 0 (1 µmol/L to 1 mol/L)
            log_chlorine_mol = max(-6, min(log_chlorine_mol, 0))
            chlorine_mol_L = 10 ** log_chlorine_mol
            _LOGGER.debug(" - chlorine_mol_L: %s", chlorine_mol_L)

            # Convert mol/L to ppm (chlorine atomic mass 35.45 g/mol)
            chlorine_ppm = chlorine_mol_L * 35.45 * 1000
            _LOGGER.debug(" - raw chlorine_ppm: %s", chlorine_ppm)

            # Salinity adjustment (if provided)
            if raw_ec != 0 and smooth_salt is not None:
                # smooth_salt expected in ppm (mg/L)
                salt_factor = max(0.7, 1.0 - smooth_salt / 50000.0)  
                chlorine_ppm *= salt_factor
                _LOGGER.debug(" - salinity: %s ppm, factor: %s", smooth_salt, salt_factor)

            # Sanity checks: realistic range for pools 0 - 5 ppm
            if chlorine_ppm > 5:
                chlorine_ppm = None
            elif chlorine_ppm < 0:
                chlorine_ppm = 0.0
            else:
                chlorine_ppm = round(chlorine_ppm, 3)

            device.sensors["chlorine_raw"] = chlorine_ppm
            _LOGGER.debug("unsmoothed chlorine_ppm: %s", chlorine_ppm)

            # Smoothing over last measurements
            if chlorine_ppm is not None:
                device.chlorine_history.append(chlorine_ppm)
                if len(device.chlorine_history) > self._max_history_len:
                    device.chlorine_history.pop(0)

            if device.chlorine_history:
                chlorine_ppm_smoothed = round(sum(device.chlorine_history) / len(device.chlorine_history), 3)
            else:
                chlorine_ppm_smoothed = None

            device.sensors["chlorine"] = chlorine_ppm_smoothed
            _LOGGER.debug("smoothed chlorine_ppm: %s", chlorine_ppm_smoothed)

        except Exception as e:
            _LOGGER.warning("Chlorine estimation failed: %s", e)
            device.sensors["chlorine"] = None
            device.sensors["chlorine_raw"] = None

        # Battery
        raw_batt = int.from_bytes(data[9:11], byteorder="little")
        _LOGGER.debug("raw_batt: %s", raw_batt)
        device.sensors["battery_voltage"] = raw_batt
        BATT_MAX_MV = 3640
        BATT_MIN_MV = 2800
        batt_percent = (raw_batt - BATT_MIN_MV) / (BATT_MAX_MV - BATT_MIN_MV) * 100.0
        device.sensors["battery"] = round(max(0, min(batt_percent, 100)), 1)

        _LOGGER.debug("Sensor calculations done")
        return device

    async def update_device(
        self, ble_device: BLEDevice, skip_query=False
    ) -> BlueConnectGoDevice:
        """Connect to the device through BLE and retrieves relevant data."""
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
