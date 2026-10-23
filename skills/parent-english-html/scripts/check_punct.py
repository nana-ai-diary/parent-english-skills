# -*- coding: utf-8 -*-
"""体检 Part 2 英文的标点与大小写：句子有没有分开、有没有句中冒大写。"""
import glob, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r"<[^>]+>")
# 句中冒出来的大写词（前面是词字符，所以不是句首）
MIDCAP = re.compile(r"(?<=[\w']) +([A-Z][A-Za-z']*)")
SAFE = {"I", "I'd", "I'm", "I'll", "I've", "I'M"}
KW = ["playdough", "youtube", "ping"]

bad_en, noend, midcaps = [], [], []
for f in sorted(glob.glob(os.path.join(ROOT, "tools", "lessons", "*.json"))):
    d = json.load(io.open(f, encoding="utf-8"))
    slug = d.get("slug")
    if sys.argv[1:] and not any(a in (slug or "") for a in sys.argv[1:]):
        continue
    for b in d.get("part2") or []:
        if b.get("type") == "day":
            continue
        en = TAG.sub("", b.get("en", "")).strip()
        if not en:
            continue
        if not re.search(r"[.!?]['\"]?$", en):
            noend.append((slug, b["no"], en))
        for m in MIDCAP.finditer(en):
            w = m.group(1)
            if w in SAFE or w.lower() in ("t",):     # don't 之类
                continue
            midcaps.append((slug, b["no"], w, en[max(0, m.start()-30):m.end()+25]))

print("1) 段末缺句末标点: %d" % len(noend))
for s in noend[:12]:
    print("   [%s/%s] %s" % (s[0], s[1], s[2][-70:]))
print("\n2) 句中冒大写: %d" % len(midcaps))
for s in midcaps[:28]:
    print("   [%s/%s] %-12s … %s" % (s[0], s[1], s[2], s[3]))
