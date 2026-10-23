# -*- coding: utf-8 -*-
"""定向修补 Part 2 英文的个别瑕疵（只做「整串精确替换」，改不了就不动）。

为什么单独做一张表
------------------
管线（OCR → reseg → apply_p2）是「无脑忠实」的：它不会替你把 "But Let's" 改成
"But let's"，也不会给 "around the waist the legs" 补逗号。这类**极个别**的
瑕疵一旦写进 `rsplit.FIX` / `apply_p2.CAP_FIX`，下次全量重跑会幂等地重现；
但要是只跑过一次，直接在 lesson JSON 上打补丁更快，且不触发整课重算。

规则：
  * old 必须在 `en` 里**恰好出现一次**，否则跳过并报警；
  * 只允许改标点 / 大小写 / 去掉明显的 OCR 噪声词；
  * 不许增删被 <span> 包住的高亮词（否则 apply_marks 会丢高亮）。

用法:
  python tools/enpatch.py            # 只报告
  python tools/enpatch.py --write    # 写回并重渲染对应页面
"""
import io, json, os, re, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))

# (slug, segno, old, new)
PATCH = [
    ("08-swing", "07",
     "You want to go higher OK.", "You want to go higher? OK."),
    ("21-playground-equipment", "01",
     "SAL Let me ", "Let me "),
    ("22-feeding-baby", "06",
     "But Let's talk about what happens before that because",
     "But let's talk about what happens before that, because"),
    ("27-taking-off-clothes", "04",
     "Very nice, Let's do the ", "Very nice. Let's do the "),
    ("30-zipping-up", "01",
     ">When we have</span>", ">when we have</span>"),
    ("02-diaper-change", "08",
     "around the waist the legs to ", "around the waist, the legs, to "),
]


def main():
    write = "--write" in sys.argv
    touched = []
    for slug, no, old, new in PATCH:
        p = os.path.join(BASE, "lessons", slug + ".json")
        d = json.load(io.open(p, encoding="utf-8"))
        seg = next((b for b in d["part2"]
                    if b.get("type") != "day" and b["no"] == no), None)
        if seg is None:
            print("跳过 %s/%s（无此段）" % (slug, no))
            continue
        n = seg["en"].count(old)
        if n != 1:
            print("!! %s/%s  命中 %d 次（要求 1 次），未改" % (slug, no, n))
            continue
        seg["en"] = seg["en"].replace(old, new)
        print("OK %-26s seg%s  %r -> %r" % (slug, no, old[:38], new[:38]))
        touched.append((p, d))
    if not write:
        print("\n（未写盘；加 --write 生效）")
        return
    for p, d in touched:
        io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
        print("written", p)
    for p, d in touched:
        r = subprocess.run([sys.executable, "-B", os.path.join(BASE, "build_lesson.py"), p],
                           capture_output=True)
        out = (r.stdout + r.stderr).decode("utf-8", "ignore").strip().splitlines()
        print(out[-1] if out else "(no output)")


if __name__ == "__main__":
    main()
