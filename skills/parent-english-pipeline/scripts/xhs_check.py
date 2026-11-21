# -*- coding: utf-8 -*-
"""xhs_check.py — 小红书 / 抖音文案字数硬校验（对齐麦田 validate.mjs）。

口径（必须与麦田 lib/bundle.js 一致，否则生成的文案过不了麦田闸门）：
  - 标题：1..20 个 Unicode 码点（JS `[...s].length` == Python `len(s)`）
  - 正文：1..1000 个码点，**话题行不计入**（麦田 make-publish.mjs 的
    splitTopics 把正文最后一行「全是 #话题」拆进 topics）
  - 话题：小红书 <=10 个（平台硬限，麦田未校验但我们自己卡）
  - emoji / 生僻字按 1 码点；组合 emoji 按实际码点数（与 JS spread 一致）

块头只认白名单：文案正文里的「茴【演员】」「茴【年兽】」是内容不是块头，
绝不能像早期发布台那样拿 `【([^】]+)】` 一切了之，会把正文和置顶评论切碎。

用法:
  python xhs_check.py <xhs.txt>
  python xhs_check.py --dir <lessons 根目录>     # 批量体检
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 只认这些块名；正文里的 茴【关键词】 不在其中，不会被当块头
BLOCK_NAMES = ("主题", "推荐标题", "标题备选", "标题", "正文笔记", "正文",
               "置顶评论备选", "置顶评论", "评论", "发布前自检", "自检")
_BLOCK_RE = re.compile(r"【(" + "|".join(BLOCK_NAMES) + r")】")
_NUM_PREFIX = re.compile(r"^\s*\d+\s*[.、)]\s*")

TITLE_MAX = 20
BODY_MAX = 1000
TOPICS_MAX = 10
MIN_TITLE = 1
MIN_BODY = 1


def parse_xhs(text: str) -> dict:
    """把 xhs.txt 拆成 {titles:[], body:str, topics:[str], comments:[], ...}。
    兼容两套标签：【推荐标题】【正文笔记】【置顶评论】与
    【标题备选】【正文】【置顶评论备选】，以及 52 课的「话题：#…」写法。
    """
    hits = list(_BLOCK_RE.finditer(text))
    out: dict = {"titles": [], "body": "", "topics": [], "comments": [],
                 "topic_line_style": ""}
    if not hits:
        out["body"] = text.strip()
        out["fallback"] = "整篇当作正文（没找到任何已知块头）"
        return out

    def slice_block(i: int) -> str:
        start = hits[i].end()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        return text[start:end].strip()

    clean_line = lambda s: _NUM_PREFIX.sub("", s).strip()

    for i, h in enumerate(hits):
        name, body = h.group(1), slice_block(i)
        if "标题" in name:
            out["titles"] = [clean_line(x) for x in body.splitlines() if x.strip()]
        elif "正文" in name:
            lines = body.split("\n")
            topic_lines: list[str] = []
            keep: list[str] = []
            for ln in lines:
                s = ln.strip()
                if not s:
                    keep.append("")
                    continue
                if s.startswith("#"):
                    topic_lines.append(s)
                    out["topic_line_style"] = "hash-line"
                elif re.match(r"^话题\s*[:：]", s):
                    # 52 课写法：话题：#a #b —— 麦田不认这个，适配层会归一化成 #行
                    topic_lines.append(re.sub(r"^话题\s*[:：]\s*", "", s))
                    out["topic_line_style"] = "label-line"
                else:
                    keep.append(ln)
            out["body"] = "\n".join(keep).strip()
            for s in topic_lines:
                out["topics"] += [t.lstrip("#") for t in re.findall(r"#[^\s#]+", s)]
        elif "评论" in name:
            out["comments"] = [clean_line(x) for x in body.splitlines() if x.strip()]
    return out


def check_text(text: str) -> tuple[bool, list[str], dict]:
    """返回 (是否通过, 问题列表, 统计)。"""
    d = parse_xhs(text)
    problems: list[str] = []

    titles = d["titles"]
    if not titles:
        problems.append("缺【推荐标题】/【标题备选】块，或标题为空")
    # 2026-11-18 新格式只给 1 个标题（地道油管亲子英语 | 主题名）；老格式 3 个备选也兼容。
    # 只要求至少 1 个、每个都合规，不再强制 3 个。
    for i, t in enumerate(titles, 1):
        n = len(t)
        if n > TITLE_MAX:
            problems.append(f"标题 {i} 有 {n} 字，超过 {TITLE_MAX} 字：{t}")
        elif n < MIN_TITLE:
            problems.append(f"标题 {i} 为空")

    body = d["body"]
    n = len(body)
    if n > BODY_MAX:
        problems.append(f"正文 {n} 字，超过 {BODY_MAX} 字（超 {n - BODY_MAX} 字；话题行已排除）")
    elif n < MIN_BODY:
        problems.append("正文为空")

    n_topics = len(d["topics"])
    if n_topics > TOPICS_MAX:
        problems.append(f"话题 {n_topics} 个，超过小红书 {TOPICS_MAX} 个上限")
    if d.get("topic_line_style") == "label-line":
        problems.append("话题写成「话题：#…」，麦田不会拆进 topics 而会计入正文；"
                        "改成单独一行 #a #b #c")

    # 2026-11-18 新格式（1-2句开场 + 5句 + tag）不带置顶评论，改为可选。
    # 老格式仍给 3 条；给了就要求恰好 3 条，没给就不拦。
    if d["comments"] and len(d["comments"]) != 3:
        problems.append(f"置顶评论有 {len(d['comments'])} 条（给就给 3 条，或不写这一块）")

    stats = {
        "titles": len(titles),
        "title_lens": [len(t) for t in titles],
        "body_chars": n,
        "topics": n_topics,
        "comments": len(d["comments"]),
    }
    return (not problems), problems, stats


def check_file(path: Path) -> tuple[bool, list[str], dict]:
    if not path.exists():
        return False, [f"缺文件 {path}"], {}
    return check_text(path.read_text(encoding="utf-8", errors="replace"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--dir", help="批量体检 lessons 根目录下的 */xhs.txt")
    a = ap.parse_args()
    files: list[Path] = []
    if a.dir:
        files = sorted(Path(a.dir).glob("*/xhs.txt"))
        if not files:
            print(f"没找到 xhs.txt：{a.dir}/*/xhs.txt")
            return 2
    elif a.path:
        files = [Path(a.path)]
    else:
        ap.error("给 xhs.txt 路径，或用 --dir <lessons 根目录>")

    bad = 0
    for f in files:
        ok, problems, stats = check_file(f)
        label = f.parent.name if a.dir else str(f)
        head = (f"{label}: {'PASS' if ok else 'FAIL'} "
                f"标题{stats.get('title_lens')} 正文{stats.get('body_chars')}字 "
                f"话题{stats.get('topics')} 评论{stats.get('comments')}")
        print(head)
        for p in problems:
            print(f"  - {p}")
        bad += 0 if ok else 1
    print(f"\nRESULT: {'PASS' if not bad else 'FAIL'} ({len(files) - bad}/{len(files)})")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
