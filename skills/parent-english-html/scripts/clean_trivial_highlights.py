# -*- coding: utf-8 -*-
"""亲子英语 · 批量去除 Part2 里的「简单词高亮」（warn-only 护栏的修复动作）

复用 lint_highlights.SIMPLE 禁用词表：把每课 part2 的 en 里，
被 <span class='k ...'> 包裹、且词本身落在 SIMPLE 的 span 去掉（保留词，仅去高亮）。
词仍在正文，只是不再标重点。幂等：无变化的课不写盘。

用法:
    python tools/clean_trivial_highlights.py            # 全系列
    python tools/clean_trivial_highlights.py <slug>     # 单课
变更过的 slug 写入 tools/_cleaned_slugs.txt（供重渲染用）。
"""
import json, os, re, sys
import lint_highlights as L

BASE = os.path.dirname(os.path.abspath(__file__))
LESSON_DIR = os.path.join(BASE, "lessons")
SERIES = os.path.join(BASE, "series.json")
SPAN_RE = re.compile(r"(<span class='k[^']*'[^>]*>)(.*?)(</span>)", re.S)


def clean_en(en):
    def repl(m):
        inner = m.group(2)
        lw = re.sub(r"[^a-z]", "", inner.lower())
        return inner if lw in L.SIMPLE else m.group(0)
    return SPAN_RE.sub(repl, en)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ser = json.load(open(SERIES, encoding="utf-8"))
    changed, freed = [], 0
    for les in ser["lessons"]:
        slug = les.get("slug")
        if only and slug != only:
            continue
        path = os.path.join(LESSON_DIR, slug + ".json")
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding="utf-8"))
        dirty = False
        for it in d.get("part2", []) or []:
            if it.get("type") != "seg":
                continue
            new_en = clean_en(it.get("en", ""))
            if new_en != it.get("en", ""):
                it["en"] = new_en
                dirty = True
        if dirty:
            json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            changed.append(slug)
            print("cleaned", slug)
    with open(os.path.join(BASE, "_cleaned_slugs.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(changed))
    print("total cleaned:", len(changed))


if __name__ == "__main__":
    main()
