# -*- coding: utf-8 -*-
"""把 01 遗留手工页对齐到当前外壳。

01-newborn-morning 没有 lesson.json（早期手工页），所以 build_lesson.py 管不到它。
这个脚本只做两件事：
  1) 用当前 tools/shell.html 重新套壳（外壳里的折叠 CSS/JS、路线列数、进度上报自动跟齐）；
  2) 给正文打三处补丁：整块换「怎么用」、七章标题改名、Part 3 的 B/C/D 档折叠。
正文（hero / Part1..7 的全部内容、示例句、词表数据）原样保留，不重新转写。

用法: python tools/reskin01.py [--dry]
"""
import io, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import build_lesson as BL                                   # noqa: E402

ROOT = os.path.abspath(os.path.join(BASE, ".."))
PAGE = os.path.join(ROOT, "outputs", "亲子英语", "01-newborn-morning", "index.html")

TITLES = [
    ("Part 1</span>全篇原声 · 盲听",
     'Part 1</span>听原声<span class="opt">先盲听 · 再看视频</span>'),
    ("Part 3</span>词汇表", "Part 3</span>学词汇"),
    ("Part 4</span>场景常用句<span class=\"opt\">重点 · 背这一份就够</span>",
     'Part 4</span>学句子<span class="opt">最重要 · 妈妈可以直接说</span>'),
    ("Part 5</span>练习", "Part 5</span>练一练"),
    ("Part 6</span>避免中式英语", "Part 6</span>避开中式英语"),
    ("Part 7</span>文化贴士<span class=\"opt\">拓展 · 选读</span>",
     'Part 7</span>文化贴士<span class="opt">选学</span>'),
]


def fold_band(m):
    cls, ttl, inner = m.group(1), m.group(2), m.group(3)
    n = inner.count("<tr>") - 1                             # 减去表头那一行
    return ('<div class="band %s tog"><span>%s</span>'
            '<span class="fold-hint" data-t="点开看 %d 个">点开看 %d 个 ▸</span></div>\n'
            '  <table class="vt folded">%s</table>' % (cls, ttl, n, n, inner))


def main():
    dry = "--dry" in sys.argv
    h = io.open(PAGE, encoding="utf-8").read()

    title = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
    brand = re.search(r'<div class="brand">(.*?)</div>', h, re.S).group(1)
    kc, kf = re.search(r"const K_CHECK='([^']*)', K_FAV='([^']*)'", h).groups()
    body = h[h.find("<main>") + len("<main>"):h.rfind("</main>")].strip("\n")

    rep = []

    # ① 整块换「怎么用」（内容与课无关，直接取 build_lesson 的渲染结果）
    i = body.find('<section id="how">')
    j = body.find("</section>", i) + len("</section>")
    if i < 0 or j <= 0:
        print("!! 找不到怎么用 section"); return
    new_how = BL.render_how({})
    rep.append(("how", len(body[i:j]), len(new_how)))
    body = body[:i] + new_how + body[j:]

    # ② 七章标题
    for a, b in TITLES:
        cnt = body.count(a)
        rep.append(("title:" + a[:26], cnt, cnt))
        body = body.replace(a, b)

    # ③ Part 3 的 B/C/D 档折叠
    body, nfold = re.subn(
        r'<div class="band ([bcd])">([^<]*)</div>\s*<table class="vt">([\s\S]*?)</table>',
        fold_band, body)
    rep.append(("fold", 0, nfold))

    html = (BL.SHELL
            .replace("__TITLE__", title)
            .replace("__BRAND__", brand)
            .replace("__TOC__", BL.render_toc(()))
            .replace("__BODY__", body)
            .replace("__KEY_CHECK__", kc)
            .replace("__KEY_FAV__", kf)
            .replace("__SLUG__", "01-newborn-morning")
            .replace("__LESSON_CN__", "起床场景"))

    left = [t for t in ("__TITLE__", "__BRAND__", "__TOC__", "__BODY__", "__KEY_CHECK__",
                        "__KEY_FAV__", "__SLUG__", "__LESSON_CN__") if t in html]
    for k, a, b in rep:
        print("  %-34s %s -> %s" % (k, a, b))
    print("folded bands:", nfold, "| leftover tokens:", left or "none",
          "| chars:", len(html))
    if dry:
        print("(dry) 未写入"); return
    io.open(PAGE, "w", encoding="utf-8").write(html)
    print("written", PAGE)


if __name__ == "__main__":
    main()
