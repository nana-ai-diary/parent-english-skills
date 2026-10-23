# -*- coding: utf-8 -*-
"""按 OCR 烧录字幕修正某一课的 Part 2（逐句精听）。

现在的分段**时间点本来就和视频基本吻合**，真正坏在两处：
  ① 英文是 ASR 听写的，会听错（go ahead first -> go hunt fairies）；
  ② 每段的结束时间取的是「下一段第一行的开始」，导致最后一句被切掉近 1 秒。

所以这里不再重排段落，只做：
  1) 用 OCR 行的时间**重算每段的起止**（起 -0.40s 留起音，止 = 下一行字幕出现时，
     即该句显示窗口的末尾），保证整句放完；
  2) 用 OCR 英文替换 ASR 英文（事实源），原段的高亮按词迁移过去；
  3) 中文译文 / 段标题 / 提示 保留；只有原稿漏掉的句子才需要补中文，逐条打印出来等手改。

用法:
  python tools/merge_p2.py 20            # 只体检，不写回
  python tools/merge_p2.py 20 --write    # 写回 tools/lessons/<slug>.json
"""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r"[\u4e00-\u9fff]")
KEY_RE = re.compile(r"<span\s+class=['\"]k\s*([a-z]?)['\"]"
                    r"(?:\s+title=['\"]([^'\"]*)['\"])?\s*>(.*?)</span>", re.S)
TAG_RE = re.compile(r"<[^>]+>")

PAD_HEAD = 0.40     # 每段往前多留一点，接住起音
PAD_TAIL = 0.10     # 末尾再多留一点


def plain(s):
    return re.sub(r"\s+", " ", TAG_RE.sub("", s)).strip()


def sents(s):
    return [x for x in re.split(r"[.!?]+", plain(s)) if x.strip()]


def apply_marks(en_plain, triples):
    """把原稿的高亮 (颜色, title, 词) 重新套到 OCR 英文上"""
    out, cur, lost = "", 0, []
    for color, title, word in triples:
        i = en_plain.find(word, cur)
        if i < 0:
            lost.append(word)
            continue
        out += en_plain[cur:i]
        attr = (" class='k %s' title='%s'" % (color, title)) if title else (" class='k %s'" % color)
        out += "<span%s>%s</span>" % (attr, word)
        cur = i + len(word)
    out += en_plain[cur:]
    return out, lost


def load_lines(n):
    p = os.path.join(ROOT, "work_seg", "%s.json" % n)
    return json.load(io.open(p, encoding="utf-8"))


def main():
    n = sys.argv[1]
    write = "--write" in sys.argv
    slug = [f for f in os.listdir(os.path.join(ROOT, "tools", "lessons")) if f.startswith(n + "-")][0][:-5]
    lj = os.path.join(ROOT, "tools", "lessons", slug + ".json")
    d = json.load(io.open(lj, encoding="utf-8"))
    ocr = load_lines(n)
    lines = ocr["segs"]                      # 每行: no/en/cn/t
    line_cuts = ocr["cuts"]
    dur = ocr.get("dur")

    # 每行的「显示窗口末尾」= 下一行出现的时间
    for i, L in enumerate(lines):
        L["end"] = line_cuts[i + 1][0] if i + 1 < len(lines) else (dur or L["t"] + 2.5)

    oldsegs = [b for b in d["part2"] if b.get("type") != "day"]
    oldcuts = [list(c) for c in d["cuts"]]

    used = set()
    report = []
    newcuts = []
    for si, (seg, cut) in enumerate(zip(oldsegs, oldcuts)):
        lo, hi = cut[0] - 1.2, cut[1] + 1.2
        mine = [L for L in lines if L["no"] not in used and lo <= L["t"] <= hi]
        if not mine:                          # 往回兜一下
            mine = [L for L in lines if L["no"] not in used and abs(L["t"] - cut[0]) < 4]
        for L in mine:
            used.add(L["no"])
        if not mine:
            newcuts.append(cut)
            report.append((seg["no"], cut, cut, 0, 0, "⚠ 没有匹配到字幕行"))
            continue
        a = max(0.0, mine[0]["t"] - PAD_HEAD)
        b = mine[-1]["end"] + PAD_TAIL
        if dur:
            b = min(b, dur)
        newcuts.append([round(a, 2), round(b, 2)])

        en_plain = " ".join(L["en"] for L in mine)
        triples = [(m.group(1) or "y", m.group(2) or "", m.group(3))
                   for m in KEY_RE.finditer(seg.get("en", ""))]
        en_html, lost = apply_marks(en_plain, triples)
        seg["en"] = en_html
        # 中文覆盖度
        miss = len(sents(en_plain)) - len(sents(seg.get("cn", "")))
        report.append((seg["no"], cut, newcuts[-1], len(mine), miss, ("丢高亮 " + "/".join(lost)) if lost else ""))

    # 没被任何段认领的行
    orphan = [L for L in lines if L["no"] not in used]
    d["cuts"] = newcuts

    print("[merge] %s  OCR行=%d 段=%d  未认领行=%d" % (n, len(lines), len(oldsegs), len(orphan)))
    for no, oc, nc, nl, miss, note in report:
        mark = ""
        if miss > 0:
            mark += "  <<< 中文缺 %d 句" % miss
        if note:
            mark += "  " + note
        print("  %s  %6.2f-%-6.2f -> %6.2f-%-6.2f  行%d%s" % (no, oc[0], oc[1], nc[0], nc[1], nl, mark))
    if orphan:
        print("  未认领：")
        for L in orphan:
            print("     %s %6.2f %s | %s" % (L["no"], L["t"], L["en"][:60], L["cn"][:30]))
    if write:
        io.open(lj, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
        print("written", lj)


if __name__ == "__main__":
    main()
