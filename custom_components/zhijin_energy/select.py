"""Select platform for enum properties."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PROPERTY_DEFINITIONS
from .coordinator import ZhijinEnergyCoordinator
from .sensor import ZhijinEnergySensor

_LOGGER = logging.getLogger(__name__)

SELECT_KEYS = [
    "battery_type",
    "output_mode",
    "fz_output",
    "voltage_monitor_selected",
    "solar_model_type",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: ZhijinEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]

    selects = []
    for key in SELECT_KEYS:
        if key in coordinator.data.get("properties", {}):
            selects.append(
                ZhijinEnergySelect(coordinator, key, PROPERTY_DEFINITIONS[key])
            )

    async_add_entities(selects)


class ZhijinEnergySelect(ZhijinEnergySensor, SelectEntity):
    """Select entity."""

    def __init__(self, coordinator, key: str, config: dict) -> None:
        super().__init__(coordinator, key, config)
        self._attr_options = list(config.get("options", {}).values())
        self._value_map = config.get("options", {})

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        value = str(prop.get("value")) if prop else None
        return self._value_map.get(value)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # 反向查找value
        raw_value = None
        for val, name in self._value_map.items():
            if name == option:
                raw_value = val
                break

        if raw_value is None:
            _LOGGER.error("Unknown option: %s", option)
            return

        prop = self.coordinator.data.get("properties", {}).get(self._key)
        property_id = prop.get("property_id") if prop else None

        if property_id is None:
            _LOGGER.error("No property_id found for %s", self._key)
            return

        success = await self.coordinator.api.set_property(
            self.coordinator.device_id,
            property_id,
            raw_value,
        )

        if success:
            await self.coordinator.async_request_refresh()
