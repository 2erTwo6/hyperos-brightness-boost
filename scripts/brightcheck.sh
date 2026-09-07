#!/system/bin/sh
# brightcheck.sh v2 — 一键检测当前亮度值 + 虚拟皮肤温度
# 用法: sh /sdcard/brightcheck.sh   (adb shell / Termux / ssh 均可,无需 root)
#
# 亮度以 /sys/class/mi_display/disp-DSI-0/brightness_clone 为准 ——
# 它是面板真实 DBV 的实时镜像,与亮度滑条同步。
# 注意:/sys/class/leds/lcd-backlight/brightness 是陈旧寄存器,只在被直接写入时
# 才更新,不随滑条变化(v1 误读了它,已更正)。
# 皮肤温度 = /sys/class/thermal/thermal_message/board_sensor_temp
# (mi_thermald 虚拟皮肤传感器,即 ThermalBrightnessController 的输入)

DBV_NODE=/sys/class/mi_display/disp-DSI-0/brightness_clone
LED=/sys/class/leds/lcd-backlight
MSG=/sys/class/thermal/thermal_message

get() { cat "$1" 2>/dev/null; }

echo "━━━━━━━ 亮度 ━━━━━━━"
dbv=$(get $DBV_NODE)
max=$(get $LED/max_brightness)
[ -n "$max" ] || max=16383
if [ -n "$dbv" ]; then
    pct=$(( dbv * 100 / max ))
    echo " 当前背光(DBV): $dbv / $max  (${pct}%)"
    echo "   ↑ 实时值,与亮度滑条同步"
else
    echo " 当前背光(DBV): 读取失败 ($DBV_NODE)"
fi
logic=$(get $LED/logic_max_brightness)
echo " 逻辑上限     : ${logic:-?}  (若低于 $max 即被某层钳制)"
cap=$(get $MSG/thermal_max_brightness)
case "$cap" in
    0|"") echo " 温控限亮     : 未触发" ;;
    *)    echo " 温控限亮     : ${cap} nit(mi_thermald 51°C 兜底已触发)" ;;
esac
legacy=$(get $LED/brightness)
echo " 旧版背光节点 : ${legacy:-?}  (陈旧寄存器,不随滑条变,仅存档)"

echo "━━━━━━━ 虚拟皮肤温度 ━━━━━━━"
skin=$(get $MSG/board_sensor_temp)
if [ -n "$skin" ] && [ "$skin" -gt -100000 ] 2>/dev/null; then
    echo " 皮肤温度     : $((skin/1000)).$(((skin%1000)/100)) °C"
    echo "   (board_sensor_temp = ${skin} m°C,mi_thermald 5 向加权虚拟传感器)"
    if [ "$skin" -lt 40000 ]; then
        echo " 热限亮判级   : <40°C,温控亮度上限未介入"
    elif [ "$skin" -lt 42000 ]; then
        echo " 热限亮判级   : 40-42°C → 上限 800-1000 nit"
    elif [ "$skin" -lt 44000 ]; then
        echo " 热限亮判级   : 42-44°C → 上限 600-800 nit"
    elif [ "$skin" -lt 46000 ]; then
        echo " 热限亮判级   : 44-46°C → 上限 500-600 nit"
    elif [ "$skin" -lt 49000 ]; then
        echo " 热限亮判级   : 46-49°C → 上限 500 nit"
    else
        echo " 热限亮判级   : ≥49°C → 上限 400 nit(51°C 起 mi_thermald 兜底 160)"
    fi
else
    echo " 皮肤温度     : 读取失败 ($skin)"
fi