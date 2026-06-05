"""The Zhijin Energy integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .api import ZhijinEnergyAPI
from .const import DOMAIN
from .coordinator import ZhijinEnergyCoordinator
from .history_tracker import HistoryTracker

PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

_LOGGER = logging.getLogger(__name__)

# 历史数据拉取间隔（每5分钟）
HISTORY_FETCH_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    session = async_get_clientsession(hass)
    api = ZhijinEnergyAPI(session, entry.data[CONF_TOKEN])

    # 获取设备信息
    try:
        device_info = await api.get_device_info(entry.data["device_id"])
        _LOGGER.info("Device info: %s", device_info.get("name"))
    except Exception as err:
        _LOGGER.error("Failed to get device info: %s", err)
        device_info = {"name": "Unknown", "mac": "unknown", "online": 0}

    # 创建协调器
    coordinator = ZhijinEnergyCoordinator(
        hass, api, entry.data["device_id"], device_info
    )

    # 首次刷新（必须在 WebSocket 启动前完成，确保数据存在）
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("First refresh completed, properties: %s", 
                     len(coordinator.data.get("properties", {})))
    except Exception as err:
        _LOGGER.error("First refresh failed: %s", err)

    # 启动 WebSocket（在首次刷新之后）
    try:
        await coordinator.async_setup()
    except Exception as err:
        _LOGGER.error("WebSocket setup failed: %s", err)

    # 创建历史数据追踪器
    history = HistoryTracker(
        hass,
        entry.entry_id,
        api,
        entry.data["device_id"],
    )
    await history.async_load()

    # 首次拉取历史数据
    try:
        result = await history.fetch_and_store()
        _LOGGER.info("Initial history fetch: %s", result)
    except Exception as err:
        _LOGGER.error("Initial history fetch failed: %s", err)

    # 定时拉取历史数据任务
    async def _fetch_history_periodic(now):
        """Periodic history fetch."""
        try:
            result = await history.fetch_and_store()
            if result.get("new_records", 0) > 0:
                _LOGGER.debug(
                    "History updated: %s new records, last_id=%s",
                    result["new_records"],
                    result["last_log_id"],
                )
        except Exception as err:
            _LOGGER.error("Periodic history fetch failed: %s", err)

    history_unsub = async_track_time_interval(
        hass,
        _fetch_history_periodic,
        HISTORY_FETCH_INTERVAL,
    )

    # 存储到 hass.data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "history": history,
        "history_unsub": history_unsub,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 注册服务
    async def handle_set_property(call: ServiceCall) -> None:
        """Handle set property service."""
        device_id = call.data.get("device_id", entry.data["device_id"])
        property_key = call.data["property"]
        value = call.data["value"]

        prop = coordinator.data.get("properties", {}).get(property_key)
        if not prop or not prop.get("property_id"):
            _LOGGER.error("Property %s not found or no property_id", property_key)
            return

        await api.set_property(
            device_id,
            prop["property_id"],
            value,
        )

    async def handle_refresh(call: ServiceCall) -> None:
        """Handle refresh service."""
        await coordinator.async_request_refresh()

    async def handle_fetch_history(call: ServiceCall) -> None:
        """Handle manual history fetch."""
        result = await history.fetch_and_store()
        _LOGGER.info("Manual history fetch: %s", result)

    async def handle_get_history_stats(call: ServiceCall) -> None:
        """Get history statistics."""
        days = call.data.get("days", 7)
        stats = history.get_charge_discharge_summary(days)
        _LOGGER.info("History stats (%s days): %s", days, stats)
        hass.bus.fire(f"{DOMAIN}_history_stats", stats)

    hass.services.async_register(DOMAIN, "set_property", handle_set_property)
    hass.services.async_register(DOMAIN, "refresh_data", handle_refresh)
    hass.services.async_register(DOMAIN, "fetch_history", handle_fetch_history)
    hass.services.async_register(DOMAIN, "get_history_stats", handle_get_history_stats)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    history_unsub = entry_data["history_unsub"]

    # 取消定时任务
    history_unsub()

    # 关闭 WebSocket
    await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.services.async_remove(DOMAIN, "set_property")
        hass.services.async_remove(DOMAIN, "refresh_data")
        hass.services.async_remove(DOMAIN, "fetch_history")
        hass.services.async_remove(DOMAIN, "get_history_stats")
    return unload_ok
