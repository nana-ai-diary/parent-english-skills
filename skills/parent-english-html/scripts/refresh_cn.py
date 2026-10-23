# -*- coding: utf-8 -*-
"""对已生成的成品页重算「中文同色高亮」。

第 01 课是早期手工页、没有 tools/lessons/*.json，走不了 build_lesson 流程，
所以单独用它来把中文里的强调统一成「与英文同色的 span」体系。

  python tools/refresh_cn.py 01-newborn-morning
"""
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_lesson as BL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "亲子英语")
BLOCK = re.compile(r'(<div class="en"[^>]*>)(.*?)(</div>\s*<div class="cn">)(.*?)(</div>)', re.S)
STRIP = re.compile(r'<span class="k [a-z]?">|</span>|<strong>|</strong>')


def main():
    for slug in sys.argv[1:]:
        p = os.path.join(OUT, slug, "index.html")
        h = io.open(p, encoding="utf-8").read()
        BL.SLUG = slug
        BL.UNMATCHED.clear()
        stat = [0, 0]

        def sub(m):
            plain = STRIP.sub("", m.group(4))
            new = BL.hl_cn(plain, m.group(2), slug, "")
            stat[0] += 1
            stat[1] += len(re.findall(r'<span class="k [a-z]?">', new))
            return m.group(1) + m.group(2) + m.group(3) + new + m.group(5)

        h2 = BLOCK.sub(sub, h)
        io.open(p, "w", encoding="utf-8").write(h2)
        print("%s 段=%d 中文高亮=%d 未匹配=%d" % (slug, stat[0], stat[1], len(BL.UNMATCHED)))
        for u in BL.UNMATCHED:
            print("   未匹配: 第%s段  %s" % (u[1], u[2]))


if __name__ == "__main__":
    main()
