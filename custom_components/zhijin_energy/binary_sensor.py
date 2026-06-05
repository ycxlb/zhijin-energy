"""Binary sensor platform for Zhijin Energy."""

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PROPERTY_DEFINITIONS
from .coordinator import ZhijinEnergyCoordinator
from .sensor import ZhijinEnergySensor

_LOGGER = logging.getLogger(__name__)

BINARY_KEYS = ["solar_status", "work_status", "power_status"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator: ZhijinEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for key in BINARY_KEYS:
        if key in coordinator.data.get("properties", {}):
            sensors.append(
                ZhijinEnergyBinarySensor(coordinator, key, PROPERTY_DEFINITIONS[key])
            )

    async_add_entities(sensors)


class ZhijinEnergyBinarySensor(ZhijinEnergySensor, BinarySensorEntity):
    """Binary sensor for status."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        value = prop.get("value") if prop else None
        return str(value) in ["1", "1.0", "True", "true", "白天", "开启"]
