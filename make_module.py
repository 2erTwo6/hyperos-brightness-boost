#!/usr/bin/env python3
"""Generate 'bright' preset thermal-brightness XMLs and a KernelSU module.

Rules (agreed with user):
  - temperature bands shift +4C (bound == 100 stays 100)
  - hot-end nit caps raised per remap table (floor 400 nit)
  - add condition id=7 (copy of Default) to silence "not configured" warnings
Only touches /product/etc/displayconfig/{multi_factor,common_multi_factor}_
thermal_brightness_control.xml via systemless KSU overlay. Nothing else.
"""
import xml.etree.ElementTree as ET
import os, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.join(BASE, "original")
MOD = os.path.join(BASE, "module")
TARGET_REL = "system/product/etc/displayconfig"

# nit remap: raise hot-end, keep 1000/800 ceiling
NIT_MAP = {160: 400, 200: 400, 250: 500, 300: 500, 360: 500,
           400: 500, 500: 600, 600: 800, 700: 800, 800: 800, 1000: 1000}
TEMP_SHIFT = 4
KEEP_MAX = 100  # the terminal band bound stays

def shift_temp(v):
    v = int(v)
    return v if v >= KEEP_MAX else v + TEMP_SHIFT

def remap_nit(v):
    n = int(v)
    if n in NIT_MAP:
        return NIT_MAP[n]
    print(f"  !! unmapped nit {n}, keeping {n}")
    return n

def transform(path_in, path_out):
    tree = ET.parse(path_in)
    root = tree.getroot()
    default_item = None
    for item in root.findall("thermal-condition-item"):
        ident = item.findtext("identifier")
        if ident == "0":
            default_item = item
        for lux in item.findall("lux-temperature-pair"):
            for tp in lux.findall("temperature-brightness-pair"):
                lo = tp.find("min-inclusive"); hi = tp.find("max-exclusive")
                nit = tp.find("nit")
                lo.text = str(shift_temp(lo.text))
                hi.text = str(shift_temp(hi.text))
                nit.text = str(remap_nit(nit.text))
    # add condition 7 = Default (log shows id=7 requested repeatedly, unconfigured)
    if default_item is not None and root.find("thermal-condition-item/identifier/..") is not None:
        import copy
        c7 = copy.deepcopy(default_item)
        c7.find("identifier").text = "7"
        c7.find("description").text = "Default"
        root.append(c7)
    ET.indent(tree, space="    ")
    tree.write(path_out, encoding="utf-8", xml_declaration=True)
    # keep same declaration style as original
    with open(path_out, "r", encoding="utf-8") as f:
        body = f.read()
    if body.startswith("<?xml version='1.0' encoding='utf-8'?>"):
        body = body.replace("<?xml version='1.0' encoding='utf-8'?>",
                            "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>", 1)
        with open(path_out, "w", encoding="utf-8") as f:
            f.write(body)

def dump(path, label):
    t = ET.parse(path); r = t.getroot()
    print(f"== {label}")
    for item in r.findall("thermal-condition-item"):
        ident, desc = item.findtext("identifier"), item.findtext("description")
        rows = []
        for l in item.findall("lux-temperature-pair"):
            row = ", ".join(f"{tp.findtext('min-inclusive')}-{tp.findtext('max-exclusive')}:{tp.findtext('nit')}"
                            for tp in l.findall("temperature-brightness-pair"))
            rows.append(f"lux {l.findtext('min-inclusive')}-{l.findtext('max-exclusive')}: {row}")
        print(f"  id={ident:>4} [{desc}]")
        for row in rows:
            print(f"      {row}")

def main():
    if os.path.exists(MOD):
        shutil.rmtree(MOD)
    cfg_dir = os.path.join(MOD, TARGET_REL)
    os.makedirs(cfg_dir)
    for name in ["multi_factor_thermal_brightness_control.xml",
                 "common_multi_factor_thermal_brightness_control.xml"]:
        src = os.path.join(ORIG, name)
        dst = os.path.join(cfg_dir, name)
        transform(src, dst)
        # sanity: parseable + valid root
        ET.parse(dst)
    print("########## BEFORE (multi_factor) ##########")
    dump(os.path.join(ORIG, "multi_factor_thermal_brightness_control.xml"), "orig")
    print("########## AFTER (multi_factor) ##########")
    dump(os.path.join(cfg_dir, "multi_factor_thermal_brightness_control.xml"), "new")
    print("########## common file conditions (new) ##########")
    dump(os.path.join(cfg_dir, "common_multi_factor_thermal_brightness_control.xml"), "new-common")
    print("OK, module tree written to", cfg_dir)

if __name__ == "__main__":
    main()