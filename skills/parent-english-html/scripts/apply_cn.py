# -*- coding: utf-8 -*-
"""把重译好的 Part 2 中文写回 lessons/<slug>.json。

背景：Part 2 的英文是「OCR 烧录字幕校正 + 转录标点」拼出来的**完整原声**，
而早期手写的中文是**精简意译**，只覆盖了其中一部分句子 —— 于是中英对不上。
这个脚本负责用逐句对应的新译文覆盖旧的。

用法:
  python tools/apply_cn.py 03               # 体检：只看差异
  python tools/apply_cn.py 03 --write       # 写回

译文来源：tools/cn/<n>.json
  { "01": "第一段中文", "02": "第二段中文", ... }
只写需要改的段号；没写的段保持原样。
**必须在 tools/apply_p2.py --write 之后跑**（apply_p2 会用旧 cn 覆盖回去）。
"""
import glob, io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug_of(n):
    hits = [f for f in os.listdir(os.path.join(ROOT, "tools", "lessons"))
            if f.startswith(n + "-")]
    return hits[0][:-5] if hits else None


def main():
    n = sys.argv[1]
    write = "--write" in sys.argv
    slug = slug_of(n)
    if not slug:
        print("找不到课号 %s" % n)
        return
    cn_path = os.path.join(ROOT, "tools", "cn", "%s.json" % n)
    if not os.path.exists(cn_path):
        print("没有 tools/cn/%s.json" % n)
        return
    table = json.load(io.open(cn_path, encoding="utf-8"))
    lj = os.path.join(ROOT, "tools", "lessons", slug + ".json")
    d = json.load(io.open(lj, encoding="utf-8"))

    changed = miss = 0
    for b in d.get("part2") or []:
        if b.get("type") == "day":
            continue
        no = b.get("no")
        if no not in table:
            continue
        new = table[no].strip()
        if not new:
            continue
        old = b.get("cn", "")
        if new != old:
            changed += 1
            print("=" * 74)
            print("[%s] %s" % (no, re.sub(r"<[^>]+>", "", b.get("en", ""))[:160]))
            print("  旧: %s" % old)
            print("  新: %s" % new)
        b["cn"] = new
    for no in table:
        if not any(x.get("no") == no for x in d.get("part2") or []):
            miss += 1
            print("⚠ %s 段号 %s 在正文里不存在" % (slug, no))
    if write:
        io.open(lj, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
        print("\n[cn] %s 改了 %d 段%s" % (slug, changed, "，幽灵段 %d" % miss if miss else ""))
        print("written", lj)
    else:
        print("\n(体检模式) %s 将改 %d 段" % (slug, changed))


if __name__ == "__main__":
    main()
