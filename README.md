# hyperos-brightness-boost

放宽 HyperOS「热限亮」的 KernelSU 模块 —— 针对小米 2602BRT18C(codename `dash`,MT6991,HyperOS / Android 16)制作,思路同平台通用。

## 这是什么

HyperOS 的 `ThermalBrightnessController`(miui-services.jar,运行于 system_server)会按 **环境光 lux × 皮肤温度** 双因子表钳制屏幕最大亮度:皮肤 **36°C 就开始限**,45°C+ 限到 **160 nit**(面板峰值 1000 nit)。室内偏亮、阴天、阳光下、边充边玩时很容易踩中,表现为"亮度不够用"。

本模块用 KernelSU systemless 挂载,替换掉:

```
/product/etc/displayconfig/multi_factor_thermal_brightness_control.xml
/product/etc/displayconfig/common_multi_factor_thermal_brightness_control.xml
```

**"明亮"预设改动:**

| 皮肤温度 | 原上限 (nit) | 新上限 (nit) |
|---|---|---|
| <40°C | 600-1000 | 不限(面板峰值 1000) |
| 40-42°C | 500-1000 | 800-1000 |
| 42-44°C | 300-800 | 600-800 |
| 44-46°C | 200-500 | 500-600 |
| 46-49°C | 160-300 | 500 |
| ≥49°C | 160 | 400* |

\* mi_thermald 的 51°C 兜底(→160 nit)与电池温度限亮通道**未动**,极端情况仍会保护性压暗。

同时补充 condition id=7(与 Default 相同),消除反复刷屏的
`Thermal condition (id=7) is not configured in file` 警告。
游戏专属表(原神/星铁/云游戏/Dolby Vision)按同规则右移+上调。

## 温控其余部分 —— 完全不动

- mi_thermald(CPU/GPU/充电 PI 限流/亮度 51°C 兜底)原样
- MTK thermald(ATC 结温控制/CPU 频率表/核隔离/充电限流)原样
- 电池温度限亮通道原样
- 内核 `leds_mtk` logic_max_brightness、HBM 禁用逻辑原样

最坏情况(XML 解析失败)也只是限亮暂时失效,不会崩溃,日志可见。

## 安装

需要 KernelSU(未测 Magisk,理论上兼容 —— 标准 Magisk 模块结构)。

```bash
ksud module install thermal_brightness_loosen_v1.0.zip
# 或在 KernelSU 管理器里刷入 zip
reboot   # 必须重启:控制器只在开机时解析配置
```

## 重启后验证

```bash
# 1. overlay 生效:能看到 id=7
grep -A1 "<identifier>7</identifier>" /product/etc/displayconfig/multi_factor_thermal_brightness_control.xml

# 2. 皮肤 ≥40°C 时阈值应是 800/600/500/400(原来是 600/500/300/200)
logcat -d | grep "updateMaxThermalBrightness: get brightness threshold"

# 3. 当前 condition
dumpsys display | grep -A2 "Thermal Brightness Controller"
```

## 回滚

KernelSU 管理器停用/删除模块后重启即还原;或:

```bash
rm -rf /data/adb/modules/thermal_brightness_loosen && reboot
```

## 云控说明

HyperOS 云控可以下发同功能配置(特征键 `cloud_multi_factor_thermal_brightness_control.xml`,
控制器日志 `load thermal config from: cloud_file`)。本仓库版本**未部署自动防御**,
仅提供观察方法:

```bash
find /data -iname "*multi_factor*" 2>/dev/null
logcat -d -b all | grep -E "load thermal config from"
```

若云控介入后再考虑 `chattr +i` 或 LSPosed hook 反制。

## 重新生成 / 调力度

```bash
python3 make_module.py   # 见脚本内 TEMP_SHIFT / NIT_MAP,改完重跑即出新 zip
```

机制研究细节见 [docs/mechanism.md](docs/mechanism.md)。

## 免责声明

仅供学习研究。调整温控参数意味着高温场景下屏幕发热更明显,请自行权衡。原始 XML 来自
本机 /product 固件(版权属小米),本仓库仅存档用于复现。