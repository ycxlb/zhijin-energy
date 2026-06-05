"""Sensor platform for Zhijin Energy."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PROPERTY_DEFINITIONS
from .coordinator import ZhijinEnergyCoordinator

_LOGGER = logging.getLogger(__name__)

# 数值类型的传感器键
SENSOR_KEYS = [
    "dianya",
    "cddl",
    "fddl",
    "temperature",
    "total_power",
    "total_power_num",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: ZhijinEnergyCoordinator = entry_data["coordinator"]
    history = entry_data["history"]

    sensors = []

    # 实时数据传感器
    for key in SENSOR_KEYS:
        if key in coordinator.data.get("properties", {}):
            sensors.append(
                ZhijinEnergySensor(coordinator, key, PROPERTY_DEFINITIONS[key])
            )

    # 历史统计传感器
    sensors.append(ZhijinEnergyDailyChargeSensor(history, coordinator))
    sensors.append(ZhijinEnergyDailyDischargeSensor(history, coordinator))
    sensors.append(ZhijinEnergyVoltageRangeSensor(history, coordinator))

    async_add_entities(sensors)


class ZhijinEnergySensor(CoordinatorEntity, SensorEntity):
    """Zhijin Energy Sensor."""

    def __init__(self, coordinator, key: str, config: dict) -> None:
        super().__init__(coordinator)
        self._key = key
        self._config = config

        device_info = coordinator.data.get("device_info", {})
        self._attr_unique_id = f"{device_info.get('mac')}_{key}"
        self._attr_name = f"{device_info.get('name')} {config['name']}"
        self._attr_device_class = config.get("device_class")
        self._attr_native_unit_of_measurement = config.get("unit")
        self._attr_state_class = config.get("state_class")

        # 设备信息
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info.get("mac"))},
            "name": device_info.get("name"),
            "manufacturer": "枝晋能源",
            "model": "太阳能控制器",
            "sw_version": device_info.get("version"),
        }

    @property
    def native_value(self):
        """Return the state of the sensor."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        return prop.get("value") if prop else None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.get("device_info", {}).get("online", False)

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        prop = self.coordinator.data.get("properties", {}).get(self._key)
        if not prop:
            return {}
        attrs = {}
        if prop.get("property_id"):
            attrs["property_id"] = prop["property_id"]
        if prop.get("raw_value") is not None:
            attrs["raw_value"] = prop["raw_value"]
        return attrs


class ZhijinEnergyDailyChargeSensor(SensorEntity):
    """Sensor for daily charge energy."""

    def __init__(self, history, coordinator) -> None:
        self._history = history
        self._coordinator = coordinator
        device_info = coordinator.data.get("device_info", {})
        self._attr_unique_id = f"{device_info.get('mac')}_daily_charge"
        self._attr_name = f"{device_info.get('name')} 今日充电量"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info.get("mac"))},
            "name": device_info.get("name"),
            "manufacturer": "枝晋能源",
            "model": "太阳能控制器",
        }

    @property
    def native_value(self):
        """Return today's charge energy."""
        from datetime import datetime
        today = datetime.now().date().isoformat()
        stats = self._history.get_daily_stats(today)

        start = stats.get("total_power_start")
        end = stats.get("total_power_end")

        if start is not None and end is not None:
            return round(end - start, 3)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        from datetime import datetime
        today = datetime.now().date().isoformat()
        stats = self._history.get_daily_stats(today)

        return {
            "voltage_min": stats.get("voltage_min"),
            "voltage_max": stats.get("voltage_max"),
            "peak_charge_current": stats.get("charge_current_max"),
            "records_today": stats.get("records_count", 0),
        }


class ZhijinEnergyDailyDischargeSensor(SensorEntity):
    """Sensor for daily discharge estimate."""

    def __init__(self, history, coordinator) -> None:
        self._history = history
        self._coordinator = coordinator
        device_info = coordinator.data.get("device_info", {})
        self._attr_unique_id = f"{device_info.get('mac')}_daily_discharge"
        self._attr_name = f"{device_info.get('name')} 今日放电量(估算)"
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_device_class = "energy"
        self._attr_state_class = "total"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info.get("mac"))},
            "name": device_info.get("name"),
            "manufacturer": "枝晋能源",
            "model": "太阳能控制器",
        }

    @property
    def native_value(self):
        """Return estimated daily discharge energy."""
        from datetime import datetime
        today = datetime.now().date().isoformat()
        stats = self._history.get_daily_stats(today)

        # 简化估算：基于峰值放电电流
        peak_discharge = stats.get("discharge_current_max")
        if peak_discharge:
            # 假设平均放电电流为峰值的30%，系统电压12V，持续12小时
            avg_current = peak_discharge * 0.3
            energy_wh = avg_current * 12 * 12  # Wh
            return round(energy_wh / 1000, 3)
        return 0


class ZhijinEnergyVoltageRangeSensor(SensorEntity):
    """Sensor for daily voltage range."""

    def __init__(self, history, coordinator) -> None:
        self._history = history
        self._coordinator = coordinator
        device_info = coordinator.data.get("device_info", {})
        self._attr_unique_id = f"{device_info.get('mac')}_voltage_range"
        self._attr_name = f"{device_info.get('name')} 今日电压范围"
        self._attr_native_unit_of_measurement = "V"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_info.get("mac"))},
            "name": device_info.get("name"),
            "manufacturer": "枝晋能源",
            "model": "太阳能控制器",
        }

    @property
    def native_value(self):
        """Return current voltage."""
        return self._coordinator.data.get("properties", {}).get("dianya", {}).get("value")

    @property
    def extra_state_attributes(self):
        """Return voltage range."""
        from datetime import datetime
        today = datetime.now().date().isoformat()
        stats = self._history.get_daily_stats(today)

        return {
            "voltage_min_today": stats.get("voltage_min"),
            "voltage_max_today": stats.get("voltage_max"),
            "voltage_delta": (
                round(stats["voltage_max"] - stats["voltage_min"], 2)
                if stats.get("voltage_max") and stats.get("voltage_min")
                else None
            ),
        }
