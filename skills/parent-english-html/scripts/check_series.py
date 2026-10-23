# -*- coding: utf-8 -*-
"""校验 outputs/亲子英语 下每一课：资源是否存在、锚点是否齐全、标签是否配平。"""
import io, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SERIES = os.path.join(ROOT, "outputs", "亲子英语")

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

bad_total = 0
for name in sorted(os.listdir(SERIES)):
    d = os.path.join(SERIES, name)
    if not os.path.isdir(d) or not re.match(r"\d\d-", name):
        continue                     # covers/ 之类是素材目录，不是课
    f = os.path.join(d, "index.html")
    if not os.path.exists(f):
        print("[%s] 缺 index.html" % name); bad_total += 1; continue
    html = io.open(f, encoding="utf-8").read()
    errs = []

    # 1) 资源引用
    refs = set(re.findall(r'(?:src|href|poster)="([^"#][^"]*)"', html))
    for r in refs:
        if r.startswith(("http", "//", "data:", "mailto:")):
            continue
        if not os.path.exists(os.path.join(d, r)):
            errs.append("缺资源 " + r)

    # 2) 锚点
    ids = set(re.findall(r'id="([^"]+)"', html))
    anchors = set(re.findall(r'href="#([^"]+)"', html))
    miss = anchors - ids
    if miss:
        errs.append("锚点无对应 id: " + ",".join(sorted(miss)))

    # 3) 标签配平（简易；先剔除 script/style 内容，避免 JS 里的 a<b 被当成标签）
    stripped = re.sub(r"<script\b.*?</script>", "<script></script>", html, flags=re.S)
    stripped = re.sub(r"<style\b.*?</style>", "<style></style>", stripped, flags=re.S)
    stack = []
    for m in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*?)(/?)>", stripped):
        close, tag, attrs, selfc = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if tag in VOID or selfc:
            continue
        if tag in ("script", "style") and not close:
            # 跳到对应结束标签
            stack.append(tag)
            continue
        if close:
            if not stack or stack[-1] != tag:
                errs.append("标签不配平 </%s>，栈顶 %s" % (tag, stack[-1] if stack else "空"))
                break
            stack.pop()
        else:
            stack.append(tag)
    if stack:
        errs.append("未闭合标签: " + ",".join(stack))

    # 4) 关键结构（Part 7 文化贴士是选读，只有涉及文化背景的课才有）
    for k in ("part1", "part2", "part3", "part4", "part5", "part6"):
        if 'id="%s"' % k not in html:
            errs.append("缺 " + k)

    size = sum(os.path.getsize(os.path.join(dp, fn))
               for dp, _, fns in os.walk(d) for fn in fns)
    # 只看媒体体积
    med = sum(os.path.getsize(os.path.join(dp, fn))
              for dp, _, fns in os.walk(d) for fn in fns
              if fn.rsplit(".", 1)[-1].lower() in ("mp3", "mp4", "jpg", "png", "jpeg", "webp"))
    print("[%-24s] %s  媒体 %.2f MB" % (name, "OK" if not errs else "!! " + " | ".join(errs), med / 1048576))
    bad_total += len(errs)

print("\n==== 问题总数:", bad_total)
