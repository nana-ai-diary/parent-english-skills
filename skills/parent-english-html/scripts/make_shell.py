# -*- coding: utf-8 -*-
"""从 01 的成品页抽出通用外壳，生成 tools/shell.html（含占位符）。"""
import io, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "..", "outputs", "亲子英语", "01-newborn-morning", "index.html")
OUT = os.path.join(BASE, "shell.html")

html = io.open(SRC, encoding="utf-8").read()
orig_len = len(html)

def cut(s, start_mark, end_mark, token, include_end=True):
    i = s.index(start_mark)
    j = s.index(end_mark, i)
    if include_end:
        j += len(end_mark)
    return s[:i] + token + s[j:]

# 1) title
html = re.sub(r"<title>.*?</title>", "<title>__TITLE__</title>", html, count=1, flags=re.S)

# 2) 目录
html = cut(html, '<nav class="toc">', "</nav>", "__TOC__")

# 3) 正文（hero 到 footer）
html = cut(html, '<div class="hero">', "</footer>", "__BODY__")

# 4) 顶栏 brand
html = re.sub(r'<div class="brand">.*?</div>\n', '<div class="brand">__BRAND__</div>\n',
              html, count=1, flags=re.S)

# 5) 存储 key
html = html.replace("const K_CHECK='nmr2.check', K_FAV='nmr2.fav';",
                    "const K_CHECK='__KEY_CHECK__', K_FAV='__KEY_FAV__';")

# 6) slug
html = html.replace("var SLUG='01-newborn-morning';", "var SLUG='__SLUG__';")

# 7) 导出文案里的课程名
html = html.replace("起床场景 · 我的复习清单", "__LESSON_CN__ · 我的复习清单")
html = html.replace("'起床笔记-数据备份-'", "'__LESSON_CN__-数据备份-'")

io.open(OUT, "w", encoding="utf-8").write(html)

missing = [t for t in ["__TITLE__", "__TOC__", "__BODY__", "__BRAND__", "__KEY_CHECK__",
                       "__KEY_FAV__", "__SLUG__", "__LESSON_CN__"] if t not in html]
print("shell.html written:", len(html), "bytes (from", orig_len, ")")
print("missing tokens:", missing or "none")
print("leftover 起床场景:", html.count("起床场景"))
