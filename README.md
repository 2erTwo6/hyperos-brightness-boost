# hyperos-brightness-boost

放宽 HyperOS「热限亮」的 KernelSU 模块 —— 针对小米 2602BRT18C(codename `dash`,MT6991,HyperOS / Android 16)制作,思路同平台通用。

**免挂载版本**:不依赖 KernelSU v3.0+ 的元模块(metamodule),也不需要 Magisk Magic Mount 基础设施 —— 模块自带 `post-fs-data.sh`,在开机早期把改好的配置**逐文件 bind mount** 到 /product 上。

## 这是什么

HyperOS 的 `ThermalBrightnessController`(miui-services.jar,运行于 system_server)会按 **环境光 lux × 皮肤温度** 双因子表钳制屏幕最大亮度:皮肤 **36°C 就开始限**,45°C+ 限到 **160 nit**(面板峰值 1000 nit)。室内偏亮、阴天、阳光下、边充边玩时很容易踩中,表现为"亮度不够用"。

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

游戏专属表(原神/星铁/云游戏/Dolby Vision)按同规则右移+上调;**condition 结构保持原样**
(不注入任何合成条件,未定义的 condition 沿用固件原生回退行为)。

## 温控其余部分 —— 完全不动

- mi_thermald(CPU/GPU/充电 PI 限流/亮度 51°C 兜底)原样
- MTK thermald(ATC 结温控制/CPU 频率表/核隔离/充电限流)原样
- 电池温度限亮通道原样
- 内核 `leds_mtk` logic_max_brightness、HBM 禁用逻辑原样

最坏情况(挂载失败)也只是限亮暂时失效,不会崩溃,`logcat -s TBL` / `logcat -s ThermalBrightnessController` 可见。

## 安装

KernelSU v3.0+(**无需元模块**)或 Magisk/APatch:

```bash
ksud module install thermal_brightness_loosen_v1.1_nomount.zip
reboot   # 必须重启:控制器只在开机时解析配置,挂载也在开机早期完成
```

工作原理:`post-fs-data.sh` 把模块内 `displayconfig/` 下的两份 XML 暂存到
`/dev/.tbl_config`(tmpfs,不暴露模块路径)后,`mount -o bind` 盖到
`/product/etc/displayconfig/` 的对应文件上 —— 发生在 system_server 读取配置之前。

## 重启后验证

```bash
# 1. 挂载生效:能看到两条 bind(源是 /dev/.tbl_config)
grep tbl_config /proc/self/mountinfo

# 2. 表内容生效:温度带右移后应出现 46-49 档(原表是 45-100)
grep -o "46-49" /product/etc/displayconfig/multi_factor_thermal_brightness_control.xml | head -1

# 3. 皮肤 ≥40°C 时阈值应是 800/600/500/400(原来是 600/500/300/200)
logcat -d | grep "updateMaxThermalBrightness: get brightness threshold"

# 4. 模块自身日志
logcat -d -s TBL
```

## 回滚

KernelSU/Magisk 管理器停用或删除模块后重启即还原(bind 挂载不持久化,重启自动消失);
卸载时的 `uninstall.sh` 也会尽力 umount。

## 检测面说明

- `mountinfo` 中会出现两条单文件 bind 记录,源路径为 `/dev/.tbl_config/...`(tmpfs),
  不泄漏 `/data/adb` 模块路径;也不会出现 overlay 分区级挂载
- 若要求完全隐藏这两条挂载记录,需要内核级方案(susfs / Kasumi LKM 等),超出本模块范围

## 云控说明

HyperOS 云控可以下发同功能配置(特征键 `cloud_multi_factor_thermal_brightness_control.xml`,
控制器日志 `load thermal config from: cloud_file`)。本仓库版本**未部署自动防御**,
仅提供观察方法:

```bash
find /data -iname "*multi_factor*" 2>/dev/null
logcat -d -b all | grep -E "load thermal config from"
```

若云控介入后再考虑反制。

## 重新生成 / 调力度

```bash
python3 make_module.py   # 见脚本内 TEMP_SHIFT / NIT_MAP,改完重跑即出新 zip
```

机制研究细节见 [docs/mechanism.md](docs/mechanism.md)。

## 免责声明

仅供学习研究。调整温控参数意味着高温场景下屏幕发热更明显,请自行权衡。原始 XML 来自
本机 /product 固件(版权属小米),本仓库仅存档用于复现。

## 更新日志

- **v1.2.1-nomount** 模块署名改为 2erTwo6
- **v1.2-nomount** 移除 condition id=7 注入,condition 结构与原生完全一致(未定义条件沿用固件回退);表值修改不变
- **v1.1-nomount** 改为免挂载脚本模块(post-fs-data 逐文件 bind mount),不再需要元模块
- v1.0 systemless overlay 版(需要 KernelSU 元模块)已被本版取代,可从 tag/历史获取