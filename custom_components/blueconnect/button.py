from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .BlueConnectGo import BlueConnectGoDevice, BlueConnectGoBluetoothDeviceData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlueConnect Go button."""
    
    coordinator: DataUpdateCoordinator[BlueConnectGoDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    async_add_entities([
        TakeMeasurementImmediately(coordinator, coordinator.data, hass, entry),
    ])


class TakeMeasurementImmediately(
    CoordinatorEntity[DataUpdateCoordinator[BlueConnectGoDevice]], ButtonEntity
):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        blueconnect_go_device: BlueConnectGoDevice,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the BlueConnect Go button."""
        super().__init__(coordinator)
        self.hass = hass
        self.entry = entry
        self.device = blueconnect_go_device

        device_name = blueconnect_go_device.name or "BlueConnect"
        name = f"{device_name} {blueconnect_go_device.identifier}"

        self._attr_unique_id = f"{name}_take_measurement".lower().replace(":", "_").replace(" ", "_")
        self._attr_name = "Take Measurement"
        self._id = blueconnect_go_device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    "bluetooth",
                    blueconnect_go_device.address,
                )
            },
            name=name,
            manufacturer="Blue Riiot",
            model="Blue Connect Go",
            hw_version=blueconnect_go_device.hw_version,
            sw_version=blueconnect_go_device.sw_version,
        )

    async def async_press(self) -> None:
        """Trigger a measurement via Bluetooth."""
        _LOGGER.info(f"Button pressed: starting measurement for {self.device.name} ({self.device.address})")

        ble_device = async_ble_device_from_address(self.hass, self.device.address)
        if not ble_device:
            _LOGGER.error(f"No Bluetooth device found at address {self.device.address}")
            raise UpdateFailed("Bluetooth device not found")

        bcgo = BlueConnectGoBluetoothDeviceData(_LOGGER)

        try:
            data = await bcgo.update_device(ble_device)
            _LOGGER.info("Measurement taken successfully.")
            self.coordinator.async_set_updated_data(data)
            _LOGGER.info("Coordinator has been updated.")
        except Exception as err:
            _LOGGER.error(f"Error while reading data: {err}")
            raise UpdateFailed(f"Error while reading data: {err}") from err
