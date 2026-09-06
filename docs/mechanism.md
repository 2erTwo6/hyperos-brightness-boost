# HyperOS 温控限亮机制研究(dash / MT6991 / Android 16)

本文记录在一次逆向排查中还原的「温度 → 亮度」完整链路,以及排除错误路径的实测过程。

## 数据流全景

```
mi_thermald (root 守护进程,每 2s)
  ├─ 皮肤虚拟温度(NTC 按 FRONT/BACK/LEFT/RIGHT/TOP 朝向加权公式)
  │     → 写 /sys/class/thermal/thermal_message/board_sensor_temp
  ├─ MONITOR-BACKLIGHT: 皮肤 ≥51°C → thermal_max_brightness=160(49°C 恢复→0)
  ├─ MONITOR-HDR: ≥40°C → super_hdr=1
  └─ 镜像当前 DBV → /sys/class/mi_display/disp-DSI-0/brightness_clone
         ↓ 拉取
system_server: com.android.server.display.ThermalBrightnessController(miui-services.jar)
  ├─ 轮询 board_sensor_temp + ThermalListener 订阅 HAL 热状态 + 光照/设置观察者
  ├─ 读 /product/etc/displayconfig/multi_factor_thermal_brightness_control.xml
  │    (lux × 皮肤温度 → 最大亮度 nit 双因子表;另有 NTC 变体与云端覆盖版)
  ├─ 与 mi_thermald 的 thermal_max_brightness 取交集 → mCurrentMaxThermalBrightness
  ├─ 多 condition 场景表(按应用: YUANSHEN/XINGTIE/CGAME/DOLBY-VISION…)
  └─ 输出上限 → DisplayPowerController 钳制 + 广播 BRIGHTNESS_THROTTLER_STATUS
         ↓
内核 leds_mtk: logic_max_brightness(满值 16383)= 最终执行闸门
/sys/class/drm/card0-DSI-1/thermal_hbm_disabled = 关闭 HBM 峰值亮度
```

关键日志特征:

```
I ThermalBrightnessController: load thermal config from: local_file
D ThermalBrightnessController: updateSkinTemperature: actual temperature: 35.549, ...
W ThermalBrightnessController: Thermal condition (id=7) is not configured in file, apply default condition!
D ThermalBrightnessController: updateMaxThermalBrightness: get brightness threshold: 600.0
```

## 双因子表(原始 Default 条件)

| 环境光 | 36-38°C | 38-40°C | 40-42°C | 42-45°C | ≥45°C |
|---|---|---|---|---|---|
| <5500 lux | 600 | 500 | 400 | 250 | 160 |
| 5500-20000 | 1000 | 600 | 500 | 300 | 200 |
| 20000-50000 | 1000 | 800 | 500 | 360 | 360 |
| >50000 | — | 1000 | 600 | 400 | 360 |

设计逻辑:越暗越早限、越热限越狠(暗处高亮刺手且耗电;阳光下为保证可读性而放宽)。

## 排除的错误路径(实测)

以下节点**都不是**钳制点,排查时不必再撞:

| 实验 | 结果 |
|---|---|
| 写 `thermal_message/thermal_max_brightness=160` 等 5s | 内核/框架均无反应 → 拉取模型 |
| tmb=160 后再写 LED `brightness=16383` | 依然 16383 → LED 驱动 sysfs 路径不消费 tmb |
| `cooling_device0`(brightness0-clone,200 档)写 160 + 触发亮度写 | 无钳制 → cdev 是镜像接口 |
| `mi_display/disp-DSI-0/brightness_clone` | 值 = 当前 DBV 镜像(852),非钳制点 |
| AOSP `BrightnessThermalClamper`(dumpsys display) | 存在但节流表为空,`mBrightnessCap:1.0`,MIUI 不走 |

关键证据:全系统字符串搜索 `thermal_max_brightness` 只命中
`/system_ext/framework/miui-services.jar`(与基路径 `/sys/class/thermal/thermal_message`
运行时拼接读取),配合 dex 方法名 `updateMaxThermalBrightness` /
`mCurrentMaxThermalBrightness` / `updateBatteryThermalBrightness`。

## 相关文件与节点速查

| 路径 | 角色 |
|---|---|
| `/product/etc/displayconfig/multi_factor_thermal_brightness_control.xml` | 限亮主表(本模块目标) |
| `/product/etc/displayconfig/common_multi_factor_thermal_brightness_control.xml` | 通用回退表 |
| `/sys/class/thermal/thermal_message/board_sensor_temp` | mi_thermald 皮肤温度输出 |
| `/sys/class/thermal/thermal_message/thermal_max_brightness` | mi_thermald 兜底上限(51°C→160) |
| `/sys/class/leds/lcd-backlight/` | 背光 LED(brightness/max 16383/logic_max_brightness) |
| `/sys/class/thermal/cooling_device0` | brightness0-clone(200 档镜像 cdev) |
| `/data/system/displayconfig/` | 云控显示类配置潜在落点 |
| `/data/vendor/thermal/config/` | mi_thermald 运行时覆盖目录 |
| `decrypt.txt`(mi_thermald 解密产物) | mi_thermald 明文策略(另见 mi-thermal-crypt 项目) |

## 附:MTK 配置混淆算法(顺带破解)

`/vendor/etc/thermal/*.conf`(MTK thermald 策略)被逐字符混淆,算法:

- 逐行处理,行内位置 `i`(0 起)做 `orig[i] = enc[i] - (i mod 10)`
- 结果 <32 时 +91 回绕(即编码端 `enc = orig + shift`,`>122` 时 `-91`)

解码脚本思路可参考同作者仓库;mi_thermald 的 `thermal-map.conf` 为另一套二进制加密,
社区有 [adithya2306/mi-thermal-crypt](https://github.com/adithya2306/mi-thermal-crypt)。