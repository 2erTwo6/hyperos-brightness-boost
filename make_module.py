#!/usr/bin/env python3
"""Generate the 'bright' preset thermal-brightness KernelSU module (mount-free variant).

Strategy: NO metamodule / NO system-dir overlay. The module ships patched XMLs and a
post-fs-data.sh that per-file bind-mounts them over /product at early boot, before
system_server parses the config. Works on KernelSU v3+ without a metamodule, and on
Magisk.

Rules (agreed with user):
  - temperature bands shift +4C (bound == 100 stays 100)
  - hot-end nit caps raised per remap table (floor 400 nit)
  - stock condition structure preserved: NO synthetic id=7 injected; undefined
    conditions keep stock fallback behavior (warning + Default)
Only touches /product/etc/displayconfig/{multi_factor,common_multi_factor}_
thermal_brightness_control.xml. Nothing else.
"""
import xml.etree.ElementTree as ET
import os, shutil, zipfile

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "original")
MOD = os.path.join(BASE, "module")

NIT_MAP = {160: 400, 200: 400, 250: 500, 300: 500, 360: 500,
           400: 500, 500: 600, 600: 800, 700: 800, 800: 800, 1000: 1000}
TEMP_SHIFT = 4
KEEP_MAX = 100

FILES = ["multi_factor_thermal_brightness_control.xml",
         "common_multi_factor_thermal_brightness_control.xml"]

POST_FS_DATA = r"""#!/system/bin/sh
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

for f in %NAMES%; do
    if mount_file "$f"; then
        log -t TBL "bound $f"
    else
        log -t TBL "FAILED to bind $f"
    fi
done
"""

UNINSTALL = r"""#!/system/bin/sh
# Best-effort cleanup; the binds also disappear on their own at reboot.
for f in %NAMES%; do
    umount "/product/etc/displayconfig/$f" 2>/dev/null
done
rm -rf /dev/.tbl_config 2>/dev/null
"""

CUSTOMIZE = r"""SKIPUNZIP=0
set_perm_recursive $MODPATH 0 0 0755 0644
set_perm $MODPATH/post-fs-data.sh 0 0 0755
set_perm $MODPATH/uninstall.sh 0 0 0755
"""

MODULE_PROP = """id=thermal_brightness_loosen
name=Thermal Brightness Loosener (mount-free)
version=v1.2-nomount
versionCode=3
author=dsh
description=Loosen HyperOS thermal brightness caps (bright preset: temp bands +4C, hot-end nits raised). Per-file bind mounts at post-fs-data - no metamodule needed. Stock condition structure preserved. Disable + reboot to restore.
"""

# ---------- XML transform ----------

def shift_temp(v):
    v = int(v)
    return v if v >= KEEP_MAX else v + TEMP_SHIFT

def remap_nit(v):
    n = int(v)
    return NIT_MAP.get(n, n)

def transform(src, dst):
    tree = ET.parse(src)
    root = tree.getroot()
    for item in root.findall("thermal-condition-item"):
        for lux in item.findall("lux-temperature-pair"):
            for tp in lux.findall("temperature-brightness-pair"):
                lo, hi, nit = tp.find("min-inclusive"), tp.find("max-exclusive"), tp.find("nit")
                lo.text = str(shift_temp(lo.text))
                hi.text = str(shift_temp(hi.text))
                nit.text = str(remap_nit(nit.text))
    ET.indent(tree, space="    ")
    tree.write(dst, encoding="utf-8", xml_declaration=True)
    with open(dst, encoding="utf-8") as f:
        body = f.read()
    body = body.replace("<?xml version='1.0' encoding='utf-8'?>",
                        "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>", 1)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(body)
    ET.parse(dst)  # sanity

# ---------- module assembly ----------

def main():
    if os.path.exists(MOD):
        shutil.rmtree(MOD)
    cfg = os.path.join(MOD, "displayconfig")
    os.makedirs(cfg)
    for name in FILES:
        transform(os.path.join(ORIG, name), os.path.join(cfg, name))

    names_sh = " \\\n         ".join(f'"{n}"' for n in FILES)
    with open(os.path.join(MOD, "post-fs-data.sh"), "w") as f:
        f.write(POST_FS_DATA.replace("%NAMES%", names_sh))
    with open(os.path.join(MOD, "uninstall.sh"), "w") as f:
        f.write(UNINSTALL.replace("%NAMES%", names_sh))
    with open(os.path.join(MOD, "customize.sh"), "w") as f:
        f.write(CUSTOMIZE)
    with open(os.path.join(MOD, "module.prop"), "w") as f:
        f.write(MODULE_PROP)

    zp = "thermal_brightness_loosen_v1.2_nomount.zip"
    with zipfile.ZipFile(os.path.join(BASE, zp), "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(MOD):
            for fn in files:
                p = os.path.join(root, fn)
                z.write(p, os.path.relpath(p, MOD))
    print("module tree:")
    for root, dirs, files in os.walk(MOD):
        for fn in sorted(files):
            print("  ", os.path.relpath(os.path.join(root, fn), MOD))
    print("zip:", zp, os.path.getsize(os.path.join(BASE, zp)), "bytes")

if __name__ == "__main__":
    main()