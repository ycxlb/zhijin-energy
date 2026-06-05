"""WebSocket client for Zhijin Energy real-time updates."""

import asyncio
import json
import logging
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from .const import (
    WS_URL,
    WS_ACTION_HEART,
    WS_ACTION_INFO_ONE,
    WS_ACTION_INFO_TWO,
    WS_HEART_INTERVAL,
    WS_RECONNECT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class ZhijinEnergyWebSocket:
    """WebSocket client for real-time device data.

    Protocol:
    1. Connect to ws://device.gz529.com
    2. Send Heart beat every 15s: {"Action":"Heart"}
    3. Send getMachinInfoOne to get real-time data
    4. Send getMachinInfoTwo + mac to get config data
    5. Server responds with {"code":200,"Action":"...","data":[...]}
    """

    def __init__(
        self,
        mac: str,
        on_data: Callable[[str, list], None],
    ) -> None:
        self._mac = mac
        self._on_data = on_data
        self._ws = None
        self._running = False
        self._task = None
        self._heartbeat_task = None

    @property
    def connected(self) -> bool:
        """Return if WebSocket is connected."""
        return self._ws is not None and self._ws.open

    async def connect(self) -> None:
        """Start WebSocket connection."""
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        if self._task:
            self._task.cancel()
            self._task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def _run(self) -> None:
        """Main WebSocket connection loop."""
        while self._running:
            try:
                _LOGGER.info("Connecting to WebSocket: %s", WS_URL)

                async with websockets.connect(
                    WS_URL,
                    additional_headers={
                        "Origin": "http://localhost",
                        "User-Agent": "okhttp/3.12.11",
                    },
                    ping_interval=None,  # 我们自己处理心跳
                ) as ws:
                    self._ws = ws
                    _LOGGER.info("WebSocket connected")

                    # 启动心跳
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop()
                    )

                    # 立即请求数据
                    await self._request_data()

                    # 接收消息
                    async for message in ws:
                        await self._handle_message(message)

            except ConnectionClosed as err:
                _LOGGER.warning("WebSocket closed: %s", err)
            except Exception as err:
                _LOGGER.error("WebSocket error: %s", err)
            finally:
                self._ws = None
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None

            if self._running:
                _LOGGER.info("Reconnecting in %ss...", WS_RECONNECT_INTERVAL)
                await asyncio.sleep(WS_RECONNECT_INTERVAL)

    async def _heartbeat_loop(self) -> None:
        """Send heartbeat periodically."""
        while self._running and self.connected:
            try:
                await self._send_json({"Action": WS_ACTION_HEART})
                await asyncio.sleep(WS_HEART_INTERVAL)
            except Exception as err:
                _LOGGER.debug("Heartbeat error: %s", err)
                break

    async def _request_data(self) -> None:
        """Request both real-time and config data."""
        # 请求实时数据 (InfoOne)
        await self._send_json({"Action": WS_ACTION_INFO_ONE})

        # 请求配置数据 (InfoTwo) - 需要 MAC 地址
        await self._send_json({
            "Action": WS_ACTION_INFO_TWO,
            "mac": self._mac,
        })

    async def _send_json(self, data: dict) -> None:
        """Send JSON message."""
        if self._ws and self._ws.open:
            await self._ws.send(json.dumps(data))
            _LOGGER.debug("WS Send: %s", data)

    async def _handle_message(self, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            _LOGGER.debug("WS Recv: %s", data)

            action = data.get("Action")
            code = data.get("code")

            # 心跳响应
            if action == WS_ACTION_HEART:
                if code == 7000:
                    _LOGGER.debug("Heartbeat OK")
                return

            # 数据响应
            if code == 200 and action in (WS_ACTION_INFO_ONE, WS_ACTION_INFO_TWO):
                properties = data.get("data", [])
                if properties:
                    await self._on_data(action, properties)
                return

        except json.JSONDecodeError:
            _LOGGER.warning("Invalid JSON: %s", message)
        except Exception as err:
            _LOGGER.error("Message handling error: %s", err)
