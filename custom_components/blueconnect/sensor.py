"""Support for BlueConnect Go ble sensors."""

from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfConductivity,
    UnitOfElectricPotential,
    UnitOfTemperature,
    EntityCategory,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .BlueConnectGo import BlueConnectGoDevice
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    "EC": SensorEntityDescription(
        key="EC",
        name="Electrical Conductivity",
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash-triangle-outline",
        suggested_display_precision=0,
    ),
    "salt": SensorEntityDescription(
        key="salt",
        name="Salt",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        suggested_display_precision=0,
    ),
    "salt_raw": SensorEntityDescription(
        key="salt_raw",
        name="Salt (Raw)",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        suggested_display_precision=0,
    ),
    "salt_grams": SensorEntityDescription(
        key="salt_grams",
        name="Salt (g/L)",
        native_unit_of_measurement="g/L",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:shaker-outline",
        entity_registry_enabled_default=False,
        suggested_display_precision=1,
    ),
    "ORP": SensorEntityDescription(
        key="ORP",
        name="Oxidation-Reduction Potential",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        icon="mdi:alpha-v-circle",
        suggested_display_precision=0,
    ),
    "pH": SensorEntityDescription(
        key="pH",
        name="pH",
        device_class=SensorDeviceClass.PH,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:ph",
        suggested_display_precision=1,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        name="Battery",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery",
        suggested_display_precision=1,
    ),
    "battery_voltage": SensorEntityDescription(
        key="battery_voltage",
        name="Battery Voltage",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        icon="mdi:battery",
        suggested_display_precision=0,
    ),
    "temperature": SensorEntityDescription(
        key="temperature",
        name="Temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        icon="mdi:pool-thermometer",
        suggested_display_precision=2,
    ),
    "chlorine": SensorEntityDescription(
        key="chlorine",
        name="Free Chlorine",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:chemical-weapon",
        suggested_display_precision=2,
    ),
    "chlorine_raw": SensorEntityDescription(
        key="chlorine_raw",
        name="Free Chlorine (Raw)",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        icon="mdi:chemical-weapon",
        suggested_display_precision=3,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BlueConnect Go BLE sensors."""

    coordinator: DataUpdateCoordinator[BlueConnectGoDevice] = hass.data[DOMAIN][entry.entry_id]
    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()
    entities = []

    device = coordinator.data
    name = f"{device.name or 'BlueConnect'} {device.identifier}"

    _LOGGER.debug("got sensors: %s", device.sensors)

    # Sensor entities
    for sensor_type, sensor_value in device.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.debug("Unknown sensor type detected: %s, %s", sensor_type, sensor_value)
            continue

        entities.append(
            BlueConnectSensor(coordinator, device, sensors_mapping[sensor_type])
        )

    # failed measurements diagnostic entity
    entities.append(BlueConnectFailedMeasurementsSensor(coordinator, device))

    async_add_entities(entities)


class BlueConnectSensor(
    CoordinatorEntity[DataUpdateCoordinator[BlueConnectGoDevice]], SensorEntity
):
    """BlueConnect BLE sensor for the device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        blueconnect_go_device: BlueConnectGoDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the BlueConnect sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = (
            f"{blueconnect_go_device.name or 'BlueConnect'} {blueconnect_go_device.identifier}"
        )
        device_id = blueconnect_go_device.address.replace(":", "_")

        self._attr_unique_id = f"{device_id}_{entity_description.key}"
        self._id = blueconnect_go_device.address
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, blueconnect_go_device.address)},
            name=name,
            manufacturer="Blue Riiot",
            model="Blue Connect",
            hw_version=blueconnect_go_device.hw_version,
            sw_version=blueconnect_go_device.sw_version,
        )

        self._consecutive_failures = 0

        # Subscribe to coordinator updates
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    @property
    def native_value(self) -> StateType:
        """Return sensor value or unavailable if three consecutive failures occur. 24 is more than 2x the sum of all sensors but less than 3x"""
        if self._consecutive_failures >= 24:
            return STATE_UNAVAILABLE

        try:
            value = self.coordinator.data.sensors[self.entity_description.key]
            if value is None:
                return STATE_UNAVAILABLE
            return value
        except KeyError:
            return STATE_UNAVAILABLE

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.native_value != STATE_UNAVAILABLE

    def _handle_coordinator_update(self) -> None:
        """Track consecutive failures based on sensor value availability."""
        key = self.entity_description.key
        value = self.coordinator.data.sensors.get(key)

        if value is None:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        self.async_write_ha_state()


class BlueConnectFailedMeasurementsSensor(
    CoordinatorEntity[DataUpdateCoordinator[BlueConnectGoDevice]], SensorEntity
):
    """Debug sensor for counting failed measurements since last success."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        blueconnect_go_device: BlueConnectGoDevice,
    ) -> None:
        """Initialize the failed measurements debug sensor."""
        super().__init__(coordinator)
        name = (
            f"{blueconnect_go_device.name or 'BlueConnect'} {blueconnect_go_device.identifier}"
        )
        device_id = blueconnect_go_device.address.replace(":", "_")

        self._attr_unique_id = f"{device_id}_failed_measurements"
        self.entity_description = SensorEntityDescription(
            key="failed_measurements",
            name="Failed Measurements",
            state_class=SensorStateClass.MEASUREMENT,
            icon="mdi:counter",
            suggested_display_precision=1,
        )
        self._id = blueconnect_go_device.address
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, blueconnect_go_device.address)},
            name=name,
            manufacturer="Blue Riiot",
            model="Blue Connect",
            hw_version=blueconnect_go_device.hw_version,
            sw_version=blueconnect_go_device.sw_version,
        )

        # We track failures globally here by listening to all sensor failures.
        self._consecutive_failures = 0

        # Subscribe to coordinator updates
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    @property
    def native_value(self) -> StateType:
        """Return number of consecutive failed measurements."""
        return self._consecutive_failures

    def _handle_coordinator_update(self) -> None:
        """Update failure count by checking all sensor values."""
        # Count how many sensors have missing or None values this update
        data = self.coordinator.data.sensors

        # Consider failure if ANY sensor is None
        if any(value is None for value in data.values()):
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 0

        self.async_write_ha_state()
