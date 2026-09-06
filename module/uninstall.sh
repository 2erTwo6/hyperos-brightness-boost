#!/system/bin/sh
# Best-effort cleanup; the binds also disappear on their own at reboot.
for f in "multi_factor_thermal_brightness_control.xml" \
         "common_multi_factor_thermal_brightness_control.xml"; do
    umount "/product/etc/displayconfig/$f" 2>/dev/null
done
rm -rf /dev/.tbl_config 2>/dev/null
