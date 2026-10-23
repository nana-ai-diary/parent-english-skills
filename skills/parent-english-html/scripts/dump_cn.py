# -*- coding: utf-8 -*-
"""dump 某几课的 Part2 段落：英文（带高亮释义）+ 现有中文，供重译时对照。"""
import glob, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = re.compile(r"<span\s+class=['\"]k\s*[a-z]?['\"](?:\s+title=['\"]([^'\"]*)['\"])?\s*>(.*?)</span>", re.S)
args = sys.argv[1:]

for f in sorted(glob.glob(os.path.join(ROOT, "tools", "lessons", "*.json"))):
    d = json.load(io.open(f, encoding="utf-8"))
    slug = d.get("slug") or ""
    if args and not any(a in slug for a in args):
        continue
    print("#" * 72)
    print("###", slug)
    for b in d.get("part2") or []:
        if b.get("type") == "day":
            print("\n== %s == %s" % (b["id"], b.get("t", "")))
            continue
        en = b.get("en", "")
        hl = ["%s=%s" % (m.group(2), m.group(1)) for m in KEY.finditer(en) if m.group(1)]
        plain = re.sub(r"<[^>]+>", "", en)
        print("\n[%s] %s" % (b["no"], plain))
        if hl:
            print("     高亮: " + "; ".join(hl))
        print("     现中文: %s" % (b.get("cn", "") or "(空)"))
