"""History data tracker for Zhijin Energy.

定时拉取远程历史日志数据并保存到本地，用于分析充电/放电趋势。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "{entry_id}_history"

# 需要追踪的历史数据字段
HISTORY_TRACKED_KEYS = [
    "dianya",      # 电池电压
    "cddl",        # 充电电流
    "fddl",        # 放电电流
    "temperature", # 温度
    "total_power", # 累计充电量
    "solar_status",    # 太阳能板状态
    "work_status",     # 负载状态
    "power_status",    # 风力状态
]


class HistoryTracker:
    """Track and store historical device data over time."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        api,
        device_id: int,
    ) -> None:
        self.hass = hass
        self.api = api
        self.device_id = device_id
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry_id))
        self._data: dict[str, Any] = {
            "last_log_id": 0,
            "records": [],
            "daily_stats": {},
        }
        self._max_records = 10000  # 最大保留记录数
        self._cleanup_interval = 100  # 每100条清理一次

    async def async_load(self) -> None:
        """Load stored history data."""
        stored = await self._store.async_load()
        if stored:
            self._data = stored
            _LOGGER.info(
                "Loaded %s history records, last_log_id=%s",
                len(self._data.get("records", [])),
                self._data.get("last_log_id", 0),
            )

    async def async_save(self) -> None:
        """Save history data to storage."""
        await self._store.async_save(self._data)

    async def fetch_and_store(self) -> dict:
        """Fetch remote logs and store new records.

        Returns summary of fetched data.
        """
        try:
            result = await self.api.get_device_logs(
                self.device_id,
                self._data.get("last_log_id", 0),
            )

            log_list = result.get("data", {}).get("list", [])
            if not log_list:
                return {"fetched": 0, "new_records": 0}

            new_records = []
            latest_log_id = self._data.get("last_log_id", 0)

            for log_entry in reversed(log_list):  # 按时间正序处理
                log_id = log_entry.get("id")
                if log_id and log_id > latest_log_id:
                    latest_log_id = log_id

                timestamp = log_entry.get("createtime_text", "")
                child_list = log_entry.get("childList", [])

                # 解析日志中的属性值
                record = {
                    "timestamp": timestamp,
                    "log_id": log_id,
                    "unix_time": self._parse_time(timestamp),
                }

                for item in child_list:
                    name = item.get("name", "")
                    value_text = item.get("value_text", "")

                    # 映射名称到 unikey
                    unikey = self._name_to_unikey(name)
                    if unikey and unikey in HISTORY_TRACKED_KEYS:
                        parsed_value = self._parse_value(value_text, unikey)
                        record[unikey] = parsed_value

                new_records.append(record)

            # 更新 last_log_id
            end_id = result.get("data", {}).get("end_id", latest_log_id)
            if end_id > self._data.get("last_log_id", 0):
                self._data["last_log_id"] = end_id

            # 添加新记录
            if new_records:
                self._data["records"].extend(new_records)

                # 清理旧记录
                if len(self._data["records"]) > self._max_records:
                    self._data["records"] = self._data["records"][-self._max_records:]

                # 更新每日统计
                self._update_daily_stats(new_records)

                # 保存
                await self.async_save()

            return {
                "fetched": len(log_list),
                "new_records": len(new_records),
                "last_log_id": self._data["last_log_id"],
            }

        except Exception as err:
            _LOGGER.error("Failed to fetch history: %s", err)
            return {"fetched": 0, "new_records": 0, "error": str(err)}

    def _name_to_unikey(self, name: str) -> str | None:
        """Map Chinese name to unikey."""
        name_map = {
            "电池当前电压": "dianya",
            "充电电流": "cddl",
            "放电电流": "fddl",
            "温度": "temperature",
            "累计充电量": "total_power",
            "太阳能板工作状态": "solar_status",
            "负载工作状态": "work_status",
            "风力发电状态": "power_status",
        }
        return name_map.get(name)

    def _parse_value(self, value_text: str, unikey: str) -> float | int | str | None:
        """Parse value text to appropriate type."""
        if not value_text:
            return None

        # 移除单位后缀
        clean = value_text.replace("V", "").replace("A", "").replace("℃", "")                           .replace("KWH", "").replace("次", "").replace("h", "")                           .replace("m", "").replace("Hz", "").strip()

        # 布尔/状态值
        if unikey in ["solar_status", "work_status", "power_status"]:
            if value_text in ["开启", "白天", "1"]:
                return 1
            elif value_text in ["关闭", "0"]:
                return 0
            return value_text

        # 数值
        try:
            val = float(clean)
            if val == int(val):
                return int(val)
            return val
        except ValueError:
            return value_text

    def _parse_time(self, time_str: str) -> int:
        """Parse time string to unix timestamp."""
        try:
            dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
            return int(dt.timestamp())
        except ValueError:
            return 0

    def _update_daily_stats(self, records: list) -> None:
        """Update daily statistics."""
        for record in records:
            timestamp = record.get("timestamp", "")
            if not timestamp:
                continue

            date = timestamp[:10]  # YYYY-MM-DD
            if date not in self._data["daily_stats"]:
                self._data["daily_stats"][date] = {
                    "records_count": 0,
                    "voltage_min": None,
                    "voltage_max": None,
                    "charge_current_max": None,
                    "discharge_current_max": None,
                    "temp_min": None,
                    "temp_max": None,
                    "total_power_start": None,
                    "total_power_end": None,
                }

            stats = self._data["daily_stats"][date]
            stats["records_count"] += 1

            # 电压统计
            voltage = record.get("dianya")
            if voltage is not None:
                if stats["voltage_min"] is None or voltage < stats["voltage_min"]:
                    stats["voltage_min"] = voltage
                if stats["voltage_max"] is None or voltage > stats["voltage_max"]:
                    stats["voltage_max"] = voltage

            # 电流统计
            charge = record.get("cddl")
            if charge is not None:
                if stats["charge_current_max"] is None or charge > stats["charge_current_max"]:
                    stats["charge_current_max"] = charge

            discharge = record.get("fddl")
            if discharge is not None:
                if stats["discharge_current_max"] is None or discharge > stats["discharge_current_max"]:
                    stats["discharge_current_max"] = discharge

            # 温度统计
            temp = record.get("temperature")
            if temp is not None:
                if stats["temp_min"] is None or temp < stats["temp_min"]:
                    stats["temp_min"] = temp
                if stats["temp_max"] is None or temp > stats["temp_max"]:
                    stats["temp_max"] = temp

            # 电量统计
            power = record.get("total_power")
            if power is not None:
                if stats["total_power_start"] is None:
                    stats["total_power_start"] = power
                stats["total_power_end"] = power

    def get_records(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list:
        """Get filtered records."""
        records = self._data.get("records", [])

        if start_time:
            start_ts = int(start_time.timestamp())
            records = [r for r in records if r.get("unix_time", 0) >= start_ts]

        if end_time:
            end_ts = int(end_time.timestamp())
            records = [r for r in records if r.get("unix_time", 0) <= end_ts]

        return records[-limit:]

    def get_daily_stats(self, date: str | None = None) -> dict:
        """Get daily statistics."""
        stats = self._data.get("daily_stats", {})
        if date:
            return stats.get(date, {})
        return stats

    def get_charge_discharge_summary(self, days: int = 7) -> dict:
        """Get charge/discharge summary for recent days.

        Returns:
            {
                "daily": [
                    {
                        "date": "2026-06-05",
                        "charge_energy_kwh": 0.5,  # 估算充电量
                        "discharge_energy_kwh": 0.2,  # 估算放电量
                        "voltage_range": [12.5, 14.2],
                        "peak_charge_current": 2.0,
                        "peak_discharge_current": 0.6,
                    }
                ],
                "total_charge_7d": 3.5,
                "total_discharge_7d": 1.2,
            }
        """
        today = datetime.now().date()
        daily = []
        total_charge = 0
        total_discharge = 0

        for i in range(days):
            date = (today - timedelta(days=i)).isoformat()
            stats = self._data.get("daily_stats", {}).get(date, {})

            if not stats or stats.get("records_count", 0) == 0:
                continue

            # 估算日充电量（基于累计电量差值）
            charge_energy = 0
            if stats.get("total_power_end") and stats.get("total_power_start"):
                charge_energy = stats["total_power_end"] - stats["total_power_start"]
                total_charge += charge_energy

            # 估算日放电量（基于放电电流积分，简化处理）
            # 实际计算需要更精确的电流-时间积分
            discharge_energy = 0
            if stats.get("discharge_current_max"):
                # 简化估算：假设平均放电电流为峰值的30%，持续12小时
                avg_discharge = stats["discharge_current_max"] * 0.3
                # 假设系统电压12V
                discharge_energy = (avg_discharge * 12 * 12) / 1000  # kWh
                total_discharge += discharge_energy

            daily.append({
                "date": date,
                "charge_energy_kwh": round(charge_energy, 3),
                "discharge_energy_kwh": round(discharge_energy, 3),
                "voltage_range": [
                    stats.get("voltage_min"),
                    stats.get("voltage_max"),
                ],
                "peak_charge_current": stats.get("charge_current_max"),
                "peak_discharge_current": stats.get("discharge_current_max"),
                "temp_range": [
                    stats.get("temp_min"),
                    stats.get("temp_max"),
                ],
                "records": stats.get("records_count", 0),
            })

        return {
            "daily": daily,
            "total_charge_kwh": round(total_charge, 3),
            "total_discharge_kwh": round(total_discharge, 3),
        }
