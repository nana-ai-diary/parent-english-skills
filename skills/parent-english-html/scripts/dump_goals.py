# -*- coding: utf-8 -*-
"""体检「今日只掌握 N 句」：长度分布 / 最长句 / 缺句末标点的断尾句。

用法：
    python -B tools/dump_goals.py            # 全系列体检
    python -B tools/dump_goals.py 03 14      # 只看含 03 / 14 的课
出现长句或断尾句时，去 tools/goals.json 给那一课手写覆盖。
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_lesson as B  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LONG = 16          # 超过这个词数就算「太长」
args = sys.argv[1:]

rows = []
for f in sorted(glob.glob(os.path.join(BASE, "tools", "lessons", "*.json"))):
    d = json.load(open(f, encoding="utf-8"))
    slug = d.get("slug") or os.path.basename(f)[:-5]
    if args and not any(a in slug for a in args):
        continue
    g = B.day_goals(d.get("part2") or [], B.load_hand_goals(slug))
    for did in sorted(g):
        for s in g[did]:
            t = B.plain(s).strip()
            rows.append((slug, did, len(t.split()), t))

print("Day 目标总句数: %d" % len(rows))
hist = {}
for r in rows:
    hist[r[2] // 4 * 4] = hist.get(r[2] // 4 * 4, 0) + 1
print("长度分布:")
for k in sorted(hist):
    print("   %2d-%2d 词 : %d" % (k, k + 3, hist[k]))

bad = [r for r in rows if r[2] > LONG]
print("\n太长(>%d词): %d" % (LONG, len(bad)))
for r in bad:
    print("   %2dw [%s/%s] %s" % (r[2], r[0], r[1], r[3]))

nop = [r for r in rows if r[3] and r[3][-1] not in ".!?"]
print("\n缺句末标点(断尾): %d" % len(nop))
for r in nop:
    print("   [%s/%s] %s" % (r[0], r[1], r[3]))

print("\n最长 10 句:")
for r in sorted(rows, key=lambda x: -x[2])[:10]:
    print("   %2dw [%s/%s] %s" % (r[2], r[0], r[1], r[3]))
