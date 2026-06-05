"""DataUpdateCoordinator for Zhijin Energy."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZhijinEnergyAPI, APIError
from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    PROPERTY_DEFINITIONS,
    WS_ACTION_INFO_ONE,
    WS_ACTION_INFO_TWO,
)
from .websocket import ZhijinEnergyWebSocket

_LOGGER = logging.getLogger(__name__)


class ZhijinEnergyCoordinator(DataUpdateCoordinator):
    """Coordinator to manage data fetching via HTTP polling and WebSocket."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ZhijinEnergyAPI,
        device_id: int,
        device_info: dict,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.api = api
        self.device_id = device_id
        self._device_info = device_info
        self._last_log_id = 0
        self._config_map = {}  # unikey -> {property_id, ...}
        self._ws = None
        self._ws_connected = False

        # 初始化数据结构
        self._data = {
            "device_info": self._parse_device_info(device_info),
            "properties": {},
        }

    def _parse_device_info(self, info: dict) -> dict:
        """Parse device info from API response."""
        return {
            "name": info.get("name"),
            "mac": info.get("mac"),
            "online": info.get("online") == 1,
            "signal": info.get("signal"),
            "version": info.get("version"),
            "latitude": info.get("address", {}).get("latitude"),
            "longitude": info.get("address", {}).get("longitude"),
        }

    async def async_setup(self) -> None:
        """Setup coordinator and start WebSocket."""
        # 首次 HTTP 拉取获取完整数据
        await self.async_config_entry_first_refresh()

        # 启动 WebSocket
        mac = self._data["device_info"].get("mac")
        if mac:
            self._ws = ZhijinEnergyWebSocket(mac, self._on_ws_data)
            await self._ws.connect()

    async def async_shutdown(self) -> None:
        """Shutdown coordinator."""
        if self._ws:
            await self._ws.disconnect()
            self._ws = None

    @callback
    async def _on_ws_data(self, action: str, properties: list) -> None:
        """Handle WebSocket data update."""
        updated = False

        for item in properties:
            unikey = item.get("unikey")
            if not unikey or unikey not in PROPERTY_DEFINITIONS:
                continue

            config = PROPERTY_DEFINITIONS[unikey]
            raw_value = item.get("value")
            property_id = item.get("property_id")

            # 数值转换
            value = self._convert_value(raw_value, config)

            # 更新属性
            self._data["properties"][unikey] = {
                "value": value,
                "raw_value": raw_value,
                "name": item.get("name"),
                "datatype": item.get("datatype"),
                "definition": item.get("definition"),
                "property_id": property_id,
                "ws_action": action,
            }

            # 更新 config_map
            if property_id:
                self._config_map[unikey] = {
                    "property_id": property_id,
                    "value": raw_value,
                }

            updated = True

        if updated:
            _LOGGER.debug("WebSocket data updated, notifying listeners")
            self.async_update_listeners()

    def _convert_value(self, raw_value, config: dict):
        """Convert raw value based on config."""
        if raw_value is None:
            return None

        convert = config.get("convert", 1)

        if isinstance(raw_value, (int, float, str)):
            try:
                value = float(raw_value) / convert
                if value == int(value):
                    value = int(value)
                return value
            except (ValueError, TypeError):
                return raw_value
        return raw_value

    async def _async_update_data(self) -> dict:
        """Fetch data from HTTP API (fallback when WS disconnected)."""
        # 如果 WebSocket 已连接，跳过 HTTP 轮询
        if self._ws and self._ws.connected:
            _LOGGER.debug("WebSocket connected, skipping HTTP poll")
            return self._data

        try:
            info = await self.api.get_device_info(self.device_id)
            self._data["device_info"] = self._parse_device_info(info)

            # 解析属性数据
            property_data = info.get("property_data", {})

            for key, prop_def in property_data.items():
                if key not in PROPERTY_DEFINITIONS:
                    continue

                config = PROPERTY_DEFINITIONS[key]
                raw_value = prop_def.get("value")
                value = self._convert_value(raw_value, config)

                self._data["properties"][key] = {
                    "value": value,
                    "raw_value": raw_value,
                    "name": prop_def.get("name"),
                    "datatype": prop_def.get("datatype"),
                    "definition": prop_def.get("definition"),
                    "property_id": self._config_map.get(key, {}).get("property_id"),
                }

            return self._data

        except APIError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_property_id(self, unikey: str) -> int | None:
        """Get property_id for a given unikey."""
        return self._config_map.get(unikey, {}).get("property_id")
