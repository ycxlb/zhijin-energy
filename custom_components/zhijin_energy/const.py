"""Constants for the Zhijin Energy integration."""

DOMAIN = "zhijin_energy"

# API Endpoints
BASE_URL = "http://app.gz529.com"
WS_URL = "ws://device.gz529.com"

# API Paths
API_LOGIN = "/index.php/api/user/login"
API_DEVICE_INFO = "/index.php/api/Machine/getMachInfo"
API_DEVICE_LOGS = "/index.php/api/Machine/getMacCollecLogList"
API_DEVICE_CONFIG = "/index.php/api/Machine/getMachinInfoTwo"

# WebSocket Actions
WS_ACTION_HEART = "Heart"
WS_ACTION_INFO_ONE = "getMachinInfoOne"   # 实时监测数据
WS_ACTION_INFO_TWO = "getMachinInfoTwo"   # 配置参数

# Update intervals
SCAN_INTERVAL = 30  # HTTP 轮询间隔（秒），作为 WebSocket 备用
WS_HEART_INTERVAL = 15  # WebSocket 心跳间隔（秒）
WS_RECONNECT_INTERVAL = 5  # WebSocket 重连间隔（秒）

# 数据类型映射
DATATYPE_MAP = {
    "int": "number",
    "float": "number",
    "boolean": "binary_sensor",
    "enum": "select",
}

# 属性定义（基于抓包数据）
PROPERTY_DEFINITIONS = {
    # 监测数据 (modeltype=1, 只读) - 对应 getMachinInfoOne
    "solar_model_type": {
        "name": "控制器类型",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "convert": 1,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "dianya": {
        "name": "电池当前电压",
        "unit": "V",
        "device_class": "voltage",
        "state_class": "measurement",
        "convert": 10,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "cddl": {
        "name": "充电电流",
        "unit": "A",  # 修正原API的Hz错误
        "device_class": "current",
        "state_class": "measurement",
        "convert": 10,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "fddl": {
        "name": "放电电流",
        "unit": "A",  # 修正原API的Hz错误
        "device_class": "current",
        "state_class": "measurement",
        "convert": 10,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "temperature": {
        "name": "温度",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
        "convert": 100,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "solar_status": {
        "name": "太阳能板工作状态",
        "device_class": "power",
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "work_status": {
        "name": "负载工作状态",
        "device_class": "power",
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "power_status": {
        "name": "风力发电状态",
        "device_class": "power",
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "total_power": {
        "name": "累计充电量",
        "unit": "kWh",
        "device_class": "energy",
        "state_class": "total_increasing",
        "convert": 10,
        "ws_action": WS_ACTION_INFO_ONE,
    },
    "total_power_num": {
        "name": "充电量清零次数",
        "unit": "次",
        "state_class": "total",
        "convert": 10,
        "ws_action": WS_ACTION_INFO_ONE,
    },

    # 配置参数 (可写) - 对应 getMachinInfoTwo
    "battery_type": {
        "name": "电池类型",
        "options": {
            "1": "锂电池",
            "2": "胶体电池",
            "3": "铅酸电池",
            "4": "开口铅酸",
            "5": "三元锂",
            "6": "磷酸铁锂",
            "7": "富液式",
        },
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "timing_hour": {
        "name": "定时时间（小时）",
        "unit": "h",
        "min": 0,
        "max": 12,  # 修正API定义的最大值
        "step": 1,
        "convert": 1,
        "mode": "slider",
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "timing_min": {
        "name": "定时时间（分钟）",
        "unit": "m",
        "min": 0,
        "max": 60,
        "step": 1,
        "convert": 1,
        "mode": "slider",
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "cm_voltage": {
        "name": "充满电压",
        "unit": "V",
        "device_class": "voltage",
        "min": 0,
        "max": 1000,
        "step": 0.1,
        "convert": 10,
        "mode": "box",
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "output_mode": {
        "name": "输出模式",
        "options": {
            "0": "手动模式",
            "1": "自动模式",
            "2": "定时模式",
            "3": "直出模式",
        },
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "jz_voltage": {
        "name": "截止电压",
        "unit": "V",
        "device_class": "voltage",
        "min": 0,
        "max": 1000,
        "step": 0.1,
        "convert": 10,
        "mode": "box",
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "fz_output": {
        "name": "负载输出",
        "options": {
            "0": "关闭",
            "1": "开启",
        },
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "voltage_monitor_selected": {
        "name": "电压检测选择",
        "options": {
            "0": "自动检测",
            "1": "检测12V",
            "2": "检测24V",
            "3": "检测36V",
            "4": "检测48V",
            "5": "检测60V",
            "6": "检测72V",
            "7": "检测84V",
        },
        "ws_action": WS_ACTION_INFO_TWO,
    },
    "hf_out_voltage": {
        "name": "恢复放电电压",
        "unit": "V",
        "device_class": "voltage",
        "min": 0,
        "max": 1000,
        "step": 0.1,
        "convert": 10,
        "mode": "box",
        "ws_action": WS_ACTION_INFO_TWO,
    },
}
