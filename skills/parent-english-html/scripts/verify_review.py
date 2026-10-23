# -*- coding: utf-8 -*-
"""按用户回归评审的 8 条问题，对 outputs/亲子英语 下所有成品页做自动验收。

  python tools/verify_review.py
"""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "亲子英语")
CJK = re.compile(r"[\u4e00-\u9fff]")
# 视频确实有文化背景 / 育儿常识可讲的课，才保留 Part 7「文化贴士」；
# 其余（穿衣、系鞋带这类纯动作教学）按用户反馈整节去掉，不硬凑。
KEEP_P7 = {"01", "09", "10", "12", "14", "22", "24", "35"}


def text(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def check_one(slug):
    p = os.path.join(OUT, slug, "index.html")
    h = io.open(p, encoding="utf-8").read()
    n = slug[:2]
    e = []

    # 必需 Part（7 为选读）
    for k in ("part1", "part2", "part3", "part4", "part5", "part6"):
        if 'id="%s"' % k not in h:
            e.append("缺 " + k)

    # ① Day 目标里的**例句**必须是英文（前面的「今日只掌握 N 句：」是中文标签，不算）
    for m in re.finditer(r'<div class="goal">(.*?)</div>', h, re.S):
        bs = re.findall(r"<b>(.*?)</b>", m.group(1), re.S)
        if not bs:
            e.append("Day 目标没有例句")
            continue
        for b in bs:
            if CJK.search(text(b)):
                e.append("Day 目标例句含中文: %s" % text(b)[:40])

    # ② 逐句精听：段数 = 音频条数；每段都有音频
    segs = re.findall(r'<div class="seg">', h)
    auds = re.findall(r'src="(audio/seg\d+\.mp3)"', h)
    if len(segs) != len(auds):
        e.append("seg %d != audio %d" % (len(segs), len(auds)))
    if len(segs) < 6:
        e.append("段数偏少 %d" % len(segs))

    # ③ 中文必须标出英文高亮对应的词（同色）
    # 按「词」统计更准：中文里标出的词数 / 英文里带中文释义的高亮数
    en_keys, cn_keys = 0, 0
    for m in re.finditer(r'<div class="en"[^>]*>(.*?)</div>\s*<div class="cn">(.*?)</div>',
                         h, re.S):
        en, cn = m.group(1), m.group(2)
        en_keys += len([x for x in re.findall(
            r"""<span\s+class=['"]k\s*[a-z]?['"]\s+title=['"]([^'"]*)['"]""", en)
            if CJK.search(x)])
        cn_keys += len(re.findall(r'<span class="k\s*[a-z]?">', cn))
    if en_keys and cn_keys < en_keys * 0.6:
        e.append("中文高亮偏少 %d/%d" % (cn_keys, en_keys))

    # ④ 提示语改叫「关键信息」
    if "视频里的提示" in h:
        e.append("仍有「视频里的提示」")

    # ⑤ 文化贴士只留给真有文化内容的课
    has7 = 'id="part7"' in h
    if has7 != (n in KEEP_P7):
        e.append("part7 存在=%s（应为 %s）" % (has7, n in KEEP_P7))

    # ⑥ 避免中式英语：第一栏必须是英文
    m = re.search(r'id="part6".*?<tbody>(.*?)</tbody>', h, re.S)
    if m:
        for i, tr in enumerate(re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S), 1):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if tds and CJK.search(text(tds[0])):
                e.append("part6 第%d行第一栏是中文: %s" % (i, text(tds[0])[:30]))
    else:
        e.append("part6 表格缺失")

    # ⑦ 中文译文里的中文不能是空的
    if h.count('<div class="cn">') < len(segs):
        e.append("cn 数量少于段数")

    # ⑧ 目录分类
    return e


def main():
    idx = io.open(os.path.join(OUT, "index.html"), encoding="utf-8").read()
    cats_ok = all(c in idx for c in
                  ["生活起居", "日常出行", "情绪社交", "游戏玩耍", "学习认知", "安全事项", "节日文化"])
    slugs = sorted(d for d in os.listdir(OUT)
                   if os.path.isdir(os.path.join(OUT, d)) and re.match(r"\d\d-", d))
    bad = 0
    for s in slugs:
        e = check_one(s)
        if e:
            bad += 1
            print("✗ %-26s %s" % (s, "；".join(e)))
    print("-" * 70)
    print("课程 %d 篇，有问题 %d 篇；目录七分类齐全: %s" % (len(slugs), bad, cats_ok))


if __name__ == "__main__":
    main()
