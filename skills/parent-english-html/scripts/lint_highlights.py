# -*- coding: utf-8 -*-
"""亲子英语 · 高亮词质检（warn-only，不修改、不阻断）

扫描每课 part2 里被 <span class='k ...'> 包裹的「重点高亮」词，若落在
SIMPLE 禁用词表（过于简单、不该当重点凑数的词），打印警告。
目的：防止像 help / stop / call / city / lost / safe 这类超简单词被高亮充数。

用法:
    python tools/lint_highlights.py            # 全系列审计
    python tools/lint_highlights.py 47-police-officer   # 单课
"""
import json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
LESSON_DIR = os.path.join(BASE, "lessons")
SERIES = os.path.join(BASE, "series.json")

# 过于简单、不该作为「重点高亮」凑数的词（小写整词；短语如 police officer 不会误伤）。
# 仅匹配单字/词，专有名词、物件名、非直觉动作、文化词不在表内。
SIMPLE = {
    # 基础动作/状态
    "help", "stop", "call", "come", "go", "look", "see", "find", "get", "got",
    "make", "made", "put", "take", "give", "gives", "like", "want", "need",
    "big", "small", "good", "bad", "yes", "no", "ok", "okay", "hi", "hey",
    # 指代词/系动词/冠词
    "this", "that", "here", "there", "the", "a", "an", "is", "are", "was",
    "were", "it", "we", "you", "they", "he", "she", "i", "my", "your",
    # 场景里过于直白的词
    "city", "lost", "ride", "safe", "police", "grandma", "mom", "dad",
    "baby", "car", "goes", "now", "up", "down", "out", "on", "off",
}

KEY_RE = re.compile(r"<span class='k[^']*'[^>]*>(.*?)</span>", re.S)


def words_of(en_html):
    return [m.group(1).strip() for m in KEY_RE.finditer(en_html or "")]


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ser = json.load(open(SERIES, encoding="utf-8"))
    hits = 0
    for les in ser["lessons"]:
        slug = les.get("slug")
        if only and slug != only:
            continue
        path = os.path.join(LESSON_DIR, slug + ".json")
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding="utf-8"))
        flagged = []
        for it in d.get("part2", []) or []:
            if it.get("type") != "seg":
                continue
            for w in words_of(it.get("en", "")):
                lw = re.sub(r"[^a-z]", "", w.lower())
                if lw in SIMPLE:
                    flagged.append(w)
        if flagged:
            hits += 1
            seen = []
            for w in flagged:
                if w not in seen:
                    seen.append(w)
            print("%-22s 高亮含简单词: %s" % (slug, " / ".join(seen)))
    if hits:
        print("\n共 %d 课含简单高亮词（仅供参考，不阻断发布）" % hits)
    else:
        print("OK：无简单高亮词充数")


if __name__ == "__main__":
    main()
