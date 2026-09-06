#!/system/bin/sh
# Thermal Brightness Loosener (mount-free variant)
# Per-file bind mounts over /product, applied at post-fs-data — before
# system_server / ThermalBrightnessController parses the config.
# No metamodule required: the mounts are performed by this script itself.

MODDIR=${0%/*}
STAGE=/dev/.tbl_config
TARGET_DIR=/product/etc/displayconfig
CTX=u:object_r:system_file:s0

mkdir -p "$STAGE" 2>/dev/null

mount_file() {
    name="$1"
    src="$MODDIR/displayconfig/$name"
    tgt="$TARGET_DIR/$name"
    [ -f "$src" ] || { log -t TBL "missing $src"; return 1; }
    [ -f "$tgt" ] || { log -t TBL "missing $tgt"; return 1; }
    # stage on tmpfs so mountinfo does not leak /data/adb module paths
    cp -f "$src" "$STAGE/$name" || return 1
    chown 0:0 "$STAGE/$name"
    chmod 644 "$STAGE/$name"
    chcon "$CTX" "$STAGE/$name" 2>/dev/null
    umount "$tgt" 2>/dev/null   # idempotent re-run guard
    mount -o bind "$STAGE/$name" "$tgt"
}

for f in "multi_factor_thermal_brightness_control.xml" \
         "common_multi_factor_thermal_brightness_control.xml"; do
    if mount_file "$f"; then
        log -t TBL "bound $f"
    else
        log -t TBL "FAILED to bind $f"
    fi
done
