# 枝晋能源太阳能控制器 - Home Assistant 自定义组件

基于抓包数据逆向开发的 Home Assistant 第三方集成，支持枝晋能源(Zhijin Energy)太阳能控制器的接入。

## 功能特性

- ✅ **实时监测**：电池电压、充放电电流、温度、累计充电量
- ✅ **状态显示**：太阳能板/负载/风力发电工作状态
- ✅ **参数配置**：充满电压、截止电压、电池类型、输出模式等
- ✅ **双通道数据**：HTTP API + WebSocket 实时推送
- ✅ **心跳保活**：WebSocket 自动重连和心跳维持

## 通信协议

### HTTP API

| 功能 | 方法 | 地址 |
|------|------|------|
| 设备详情 | GET | `/api/Machine/getMachInfo?id={id}` |
| 历史日志 | GET | `/api/Machine/getMacCollecLogList?mac_id={id}&last_log_id={last_id}` |
| 配置参数 | POST | `/api/Machine/getMachinInfoTwo` |

### WebSocket 协议

```
ws://device.gz529.com

客户端 → 服务端:
  {"Action":"Heart"}                          # 心跳 (每15秒)
  {"Action":"getMachinInfoOne"}                 # 请求实时数据
  {"Action":"getMachinInfoTwo","mac":"xx:xx"}  # 请求配置参数

服务端 → 客户端:
  {"code":7000,"Action":"Heart"}                # 心跳响应
  {"code":200,"Action":"getMachinInfoOne","data":[...]}  # 实时数据
  {"code":200,"Action":"getMachinInfoTwo","data":[...]}  # 配置数据
```

## 安装

### HACS 安装（推荐）

1. 打开 HACS → 自定义仓库
2. 添加仓库地址：`https://github.com/ycxlb/zhijin_energy`
3. 选择类别：Integration
4. 安装并重启 Home Assistant

### 手动安装

1. 下载本仓库代码
2. 将 `custom_components/zhijin_energy/` 复制到您的 Home Assistant `config/custom_components/` 目录
3. 重启 Home Assistant
4. 目录结构
<pre>
zhijin-energy/
├── README.md                          # 项目说明文档
├── hacs.json                          # HACS安装配置
└── custom_components/
    └── zhijin_energy/
        ├── manifest.json              # 组件清单（域名、依赖、版本）
        ├── const.py                   # 常量定义（API地址、属性映射表）
        ├── api.py                     # HTTP API 封装（请求/响应处理）
        ├── coordinator.py             # 数据更新协调器（30秒轮询）
        ├── websocket.py               # WebSocket 实时推送客户端
        ├── config_flow.py             # 配置流程（UI配置界面）
        ├── __init__.py                # 组件入口（初始化/卸载）
        ├── sensor.py                  # 传感器实体（电压/电流/温度/电量）
        ├── binary_sensor.py           # 二进制传感器（太阳能/负载/风力状态）
        ├── number.py                  # 数值调节实体（电压阈值/定时时间）
        ├── select.py                  # 下拉选择实体（电池类型/输出模式）
        ├── services.yaml              # 服务定义（设置参数/刷新数据）
        └── strings.json               # 翻译文件（配置界面文本）
</pre>
## 配置

1. 进入 **配置 → 设备与服务 → 添加集成**
2. 搜索 "枝晋能源"
3. 输入：
   - **API Token**: 从APP抓包获取的 `token` 值
   - **设备ID**: 设备编号（如 `29999`）

## 获取 Token

通过抓包工具（如 HttpCanary、Charles）抓取APP请求头中的 `token` 字段：
```
token: 51b33c38-74e3-4444-80d7-4174444121427
```

## 实体列表

### 传感器 (Sensor) - 实时数据
| 实体 | 说明 | 单位 | 来源 |
|------|------|------|------|
| `sensor.xxx_电池当前电压` | 电池电压 | V | WebSocket/HTTP |
| `sensor.xxx_充电电流` | 充电电流 | A | WebSocket/HTTP |
| `sensor.xxx_放电电流` | 放电电流 | A | WebSocket/HTTP |
| `sensor.xxx_温度` | 设备温度 | °C | WebSocket/HTTP |
| `sensor.xxx_累计充电量` | 累计充电量 | kWh | WebSocket/HTTP |

### 二进制传感器 (Binary Sensor) - 状态
| 实体 | 说明 |
|------|------|
| `binary_sensor.xxx_太阳能板工作状态` | 太阳能板是否工作 |
| `binary_sensor.xxx_负载工作状态` | 负载是否工作 |
| `binary_sensor.xxx_风力发电状态` | 风力是否发电 |

### 数值调节 (Number) - 配置参数
| 实体 | 说明 | 范围 |
|------|------|------|
| `number.xxx_充满电压` | 充满电压阈值 | 0-1000V |
| `number.xxx_截止电压` | 截止电压阈值 | 0-1000V |
| `number.xxx_恢复放电电压` | 恢复放电电压 | 0-1000V |
| `number.xxx_定时时间（小时）` | 定时小时 | 0-12h |
| `number.xxx_定时时间（分钟）` | 定时分钟 | 0-60m |

### 下拉选择 (Select) - 枚举配置
| 实体 | 说明 | 选项 |
|------|------|------|
| `select.xxx_电池类型` | 电池类型 | 锂电池/胶体电池/铅酸电池等 |
| `select.xxx_输出模式` | 输出模式 | 手动/自动/定时/直出 |
| `select.xxx_负载输出` | 负载开关 | 关闭/开启 |
| `select.xxx_电压检测选择` | 电压检测 | 自动/12V/24V/.../84V |

## 已知问题

1. **电流单位错误**: API 返回的单位为 `Hz`，组件已修正为 `A`
2. **定时时间越界**: API 允许设置 `24h`，但定义最大值为 `12h`，组件已限制
3. **设置参数API**: 尚未抓包获取，当前 Number/Select 实体为只读模式

## 待办事项

- [ ] 抓包获取设置参数的 API 地址（在APP中修改参数时抓包）
- [ ] 支持设备自动发现
- [ ] 添加更多诊断传感器（信号强度、固件版本等）
- [ ] 添加累计电量计算（清零次数 × 1000 + 当前值）

## 免责声明

本项目为个人逆向学习，仅供学习交流，非官方集成。使用本组件产生的任何风险由用户自行承担。
