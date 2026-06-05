"""API client for Zhijin Energy."""

import json
import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    API_DEVICE_INFO,
    API_DEVICE_LOGS,
    API_DEVICE_CONFIG,
)

_LOGGER = logging.getLogger(__name__)


class ZhijinEnergyAPI:
    """API client for Zhijin Energy cloud platform."""

    def __init__(self, session: aiohttp.ClientSession, token: str) -> None:
        self._session = session
        self._token = token
        self._headers = {
            "platform": "App",
            "token": token,
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; MI 8 Build/QKQ1.190828.002; wv) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
                "Chrome/110.0.5481.154 Mobile Safari/537.36 "
                "uni-app Html5Plus/1.0 (Immersed/32.363636)"
            ),
        }

    async def _request(
        self, method: str, path: str, **kwargs
    ) -> dict[str, Any]:
        """Make API request."""
        url = f"{BASE_URL}{path}"

        headers = {**self._headers, **kwargs.pop("headers", {})}

        async with self._session.request(
            method, url, headers=headers, **kwargs
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

            if data.get("code") not in [1, 200]:
                raise APIError(f"API error: {data.get('msg')}")

            return data

    async def get_device_info(self, device_id: int) -> dict[str, Any]:
        """Get device info and current property values."""
        data = await self._request(
            "GET", 
            f"{API_DEVICE_INFO}?id={device_id}"
        )
        return data.get("data", {}).get("info", {})

    async def get_device_logs(
        self, device_id: int, last_log_id: int = 0
    ) -> dict[str, Any]:
        """Get device history logs."""
        return await self._request(
            "GET",
            f"{API_DEVICE_LOGS}?mac_id={device_id}&last_log_id={last_log_id}"
        )

    async def get_device_config(self, device_id: int) -> list[dict]:
        """Get device writable config properties.

        Returns list of config items with property_id, unikey, value, definition.
        """
        data = await self._request(
            "POST",
            API_DEVICE_CONFIG,
            json={"machine_id": device_id},
        )
        return data.get("data", [])

    async def set_property(
        self, device_id: int, property_id: int, value: Any
    ) -> bool:
        """Set device property via HTTP API.

        TODO: 需要抓包确认实际API地址和参数格式。
        当前基于常见IoT平台模式推测。

        可能的API端点:
        - POST /api/Machine/setProperty
        - POST /api/Machine/control
        - POST /api/Machine/sendCmd
        - POST /api/Machine/setMachinInfo

        推测请求体:
        {
            "machine_id": 29673,
            "property_id": 34,
            "value": 142,  // 原始值 (14.2 * 10)
            "unikey": "cm_voltage"
        }
        """
        _LOGGER.warning(
            "Property setting not yet implemented. "
            "Would set device=%s property_id=%s value=%s",
            device_id, property_id, value
        )

        # 以下为推测实现，需抓包验证:
        # try:
        #     data = await self._request(
        #         "POST",
        #         "/index.php/api/Machine/setProperty",
        #         json={
        #             "machine_id": device_id,
        #             "property_id": property_id,
        #             "value": value,
        #         },
        #     )
        #     return data.get("code") in [1, 200]
        # except APIError as err:
        #     _LOGGER.error("Failed to set property: %s", err)
        #     return False

        return False


class APIError(Exception):
    """API error."""
