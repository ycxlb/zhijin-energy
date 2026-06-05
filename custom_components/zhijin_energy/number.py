"""Number platform for configurable parameters."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PROPERTY_DEFINITIONS
from .coordinator import ZhijinEnergyCoordinator
from .sensor import ZhijinEnergySensor

NUMBER_KEYS = [
    "cm_voltage",
    "jz_voltage",
    "hf_out_voltage",
    "timing_hour",
    "timing_min",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: ZhijinEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]

    numbers = []
    for key in NUMBER_KEYS:
        if key in coordinator.data.get("properties", {}):
            numbers.append(
                ZhijinEnergyNumber(coordinator, key, PROPERTY_DEFINITIONS[key])
            )

    async_add_entities(numbers)


class ZhijinEnergyNumber(ZhijinEnergySensor, NumberEntity):
    """Number entity."""

    def __init__(self, coordinator, key: str, config: dict) -> None:
        super().__init__(coordinator, key, config)
        self._attr_native_min_value = config.get("min", 0)
        self._attr_native_max_value = config.get("max", 100)
        self._attr_native_step = config.get("step", 1)
        self._attr_mode = (
            NumberMode.SLIDER 
            if config.get("mode") == "slider" 
            else NumberMode.BOX
        )

    @property
    def native_value(self) -> float | None:
        """Return the entity value."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        value = prop.get("value") if prop else None
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        property_id = prop.get("property_id") if prop else None

        if property_id is None:
            _LOGGER.error("No property_id found for %s", self._key)
            return

        convert = self._config.get("convert", 1)
        raw_value = value * convert

        # 根据数据类型转换
        datatype = prop.get("datatype", "float")
        if datatype == "int":
            raw_value = int(raw_value)

        success = await self.coordinator.api.set_property(
            self.coordinator.device_id,
            property_id,
            raw_value,
        )

        if success:
            await self.coordinator.async_request_refresh()
