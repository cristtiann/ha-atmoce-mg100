from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AtmoceDataUpdateCoordinator
from .registers import SENSORS, AtmoceSensorDescription

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Atmoce sensors from a config entry."""
    coordinator: AtmoceDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [AtmoceSensor(coordinator, entry.entry_id, description) for description in SENSORS]
    async_add_entities(entities)

class AtmoceSensor(CoordinatorEntity[AtmoceDataUpdateCoordinator], SensorEntity):
    """Representation of an Atmoce sensor."""

    # We deliberately do not let HA compose entity IDs from device + entity name.
    # The goal is compatibility with the original YAML entities:
    # sensor.atmoce_pv_power, sensor.atmoce_battery_soc, etc.
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: AtmoceDataUpdateCoordinator,
        entry_id: str,
        description: AtmoceSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self._description = description
        self._desired_entity_id = f"sensor.{description.unique_id}"

        self.entity_id = self._desired_entity_id
        self._attr_name = description.name
        self._attr_unique_id = description.unique_id
        self._attr_native_unit_of_measurement = description.unit
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_suggested_display_precision = description.precision
        self._attr_entity_registry_enabled_default = description.enabled
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry_id)},
            "name": "Atmoce",
            "manufacturer": "Atmoce",
            "model": "MG100",
        }

    async def async_added_to_hass(self) -> None:
        """Try to keep the YAML-compatible entity ID even when registry history exists."""
        await super().async_added_to_hass()

        registry = er.async_get(self.hass)
        current_entity_id = self.entity_id
        desired_entity_id = self._desired_entity_id

        if current_entity_id == desired_entity_id:
            return

        existing = registry.async_get(desired_entity_id)
        if existing is not None and existing.unique_id != self.unique_id:
            _LOGGER.warning(
                "Cannot rename %s to %s because desired entity_id already exists. "
                "Delete or rename the old entity first.",
                current_entity_id,
                desired_entity_id,
            )
            return

        try:
            registry.async_update_entity(current_entity_id, new_entity_id=desired_entity_id)
            _LOGGER.info("Renamed Atmoce entity %s to %s", current_entity_id, desired_entity_id)
        except Exception as err:
            _LOGGER.warning("Could not rename %s to %s: %s", current_entity_id, desired_entity_id, err)

    @property
    def native_value(self):
        """Return the native sensor value."""
        return self.coordinator.data.get(self._description.key)

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {
            "modbus_address": self._description.address,
            "modbus_data_type": self._description.data_type,
        }
