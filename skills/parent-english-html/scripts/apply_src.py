# -*- coding: utf-8 -*-
"""
把「来源频道」写进唯一数据源 tools/series.json，并同步到每课 lesson JSON。

用法：
    python tools/apply_src.py            # 只写 series.json（若无 by 字段就把 CHANNELS 灌进去）
    python tools/apply_src.py --write    # 同时更新 tools/lessons/*.json 的 source / disclaim_src
    python tools/apply_src.py --check    # 只体检，不写

约定：
    series.json 的 lessons[].by 是唯一权威来源；source / disclaim_src 都由它派生，别手改。
    by 写成显示用原文：有 @ 就带 @（如 @babylist），没有就不带（如 Confucius Institute Adelaide）。
"""
import io
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
SERIES = os.path.join(BASE, "series.json")
LESSONS = os.path.join(BASE, "lessons")

# 课号 -> YouTube 频道（用户 2026-10-06 提供；01 取自其页面里既有的写法，待用户确认）
CHANNELS = {
    "01": "@SpeakEnglishWithVanessa",          # 原有，用户本轮未提，待确认
    "02": "@babylist",
    "03": "@Helping Hands Doula",
    "04": "@danygo",
    "05": "@KonaKids",
    "06": "@Penquis Autism Community Services",
    "07": "@Children's Hospital Colorado",
    "08": "@EnglishwithBrittany",
    "09": "@SpeakEnglishWithVanessa",
    "10": "@SpeakEnglishWithVanessa",
    "11": "@babylist",
    "12": "@Let's play",
    "13": "@Let's play",
    "14": "Confucius Institute Adelaide",
    "15": "@RyansWorld",
    "16": "@heidizidanezack",
    "17": "@SierraRhiaFAM",
    "18": "@RyansWorld",
    "19": "@elizabethandbriceida",
    "20": "@elizabethandbriceida",
    "21": "@elizabethandbriceida",
    "22": "@SpeakEnglishWithVanessa",
    "23": "@RubyandBonnie",
    "24": "@mamajoshandmylasfamily",
    "25": "@elizabethandbriceida",
    "26": "@GoallyApps",
    "27": "@NicklausChildrensHospital",
    "28": "@SpeakEnglishWithVanessa",
    "29": "@TheKidsplainer",
    "30": "@SuperSimplePlay",
    "31": "@SuperSimplePlay",
    "32": "@bloominbabies749",
    "33": "@bloominbabies749",
    "34": "@kidsteachtoo7609",
}

DISCLAIM = ("英文原文与视频版权归原作者（YouTube %s）所有，此处仅作学习用途整理"
            "（视频已自行剪辑并重配中英字幕）。")


def source_of(by):
    return "来源：YouTube %s" % by


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def dump(p, obj):
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def write_series(dry=True):
    d = load(SERIES)
    changed = 0
    for L in d["lessons"]:
        # series.json 里已有的 by 优先；CHANNELS 只在缺字段时当「种子」灌进去
        by = (L.get("by") or "").strip() or CHANNELS.get(L["n"])
        if by is None:
            print("!! 课号 %s（%s）没有频道，跳过" % (L["n"], L["slug"]))
            continue
        if L.get("by") == by:
            continue                      # 没变化，不重排键序
        # 插到 src 后面，保持键序稳定
        new = {}
        placed = False
        for k, v in L.items():
            if k == "by":
                continue                  # 稍后按位置重插
            new[k] = v
            if k == "src":
                new["by"] = by
                placed = True
        if not placed:                    # 没有 src 字段，兜底追加
            new["by"] = by
        L.clear()
        L.update(new)
        changed += 1
    if dry:
        print("[dry] series.json 会写入 %d 个 by 字段" % changed)
        return d
    dump(SERIES, d)
    print("series.json 已写入 %d 个 by 字段" % changed)
    return d


def write_lessons(d, dry=True):
    n_ok = n_skip = 0
    for L in d["lessons"]:
        slug, by = L["slug"], L.get("by")
        p = os.path.join(LESSONS, slug + ".json")
        if not os.path.isfile(p):
            print("-- %s 无 lesson.json（遗留手工页），跳过" % slug)
            n_skip += 1
            continue
        if not by:
            print("-- %s 无频道，跳过" % slug)
            n_skip += 1
            continue
        o = load(p)
        old_src = o.get("source")
        new_src = source_of(by)
        # 页脚：在原句基础上把频道名塞进括号里（保持句末其它声明不动）
        old_dis = o.get("disclaim_src") or ""
        m = re.search(r"版权归原作者（YouTube [^）]*）所有", old_dis)
        if m:
            new_dis = old_dis[:m.start()] + ("版权归原作者（YouTube %s）所有" % by) + old_dis[m.end():]
        elif "版权归原作者" in old_dis:
            new_dis = re.sub(r"版权归原作者[^，。]*", "版权归原作者（YouTube %s）" % by, old_dis, count=1)
        else:
            new_dis = DISCLAIM % by
        if new_src == old_src and new_dis == old_dis:
            n_skip += 1
            continue
        if dry:
            print("[dry] %-26s %s  |  %s" % (slug, new_src, new_dis[:46] + "…"))
        else:
            o["source"] = new_src
            o["disclaim_src"] = new_dis
            dump(p, o)
            print("OK  %-26s %s" % (slug, new_src))
        n_ok += 1
    print("\n%s：更新 %d 篇，跳过 %d 篇" % ("[dry]" if dry else "已写", n_ok, n_skip))


def check():
    d = load(SERIES)
    bad = []
    for L in d["lessons"]:
        by = L.get("by")
        p = os.path.join(LESSONS, L["slug"] + ".json")
        if not by:
            bad.append((L["n"], L["slug"], "series.json 缺 by"))
            continue
        if not os.path.isfile(p):
            continue
        o = load(p)
        want = source_of(by)
        if o.get("source") != want:
            bad.append((L["n"], L["slug"], "source 不一致: %r != %r" % (o.get("source"), want)))
        if by not in (o.get("disclaim_src") or ""):
            bad.append((L["n"], L["slug"], "disclaim_src 里没有频道名"))
    if bad:
        for b in bad:
            print("FAIL %s %-26s %s" % b)
        print("\n共 %d 处不一致" % len(bad))
    else:
        print("全部一致：series.json 的 by 与每课 source / disclaim_src 已对齐")
    return len(bad)


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(1 if check() else 0)
    dry = "--write" not in sys.argv
    d = write_series(dry=True)
    if not dry:
        dump(SERIES, d)
        print("series.json 已写入")
    write_lessons(d, dry=dry)
    if not dry:
        print("\n--- 自检 ---")
        check()
