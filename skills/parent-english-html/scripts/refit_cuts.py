# -*- coding: utf-8 -*-
"""重算分段切点并写回 lesson JSON（只动 `cuts`，一个字的文本都不改）。

什么时候用
----------
`apply_p2.py` 会在 `reseg` 之后自动调 `cutfit.refine()` 精修切点 —— 但它依赖
`work_prep/NN/words.json`。如果某一课当时**还没生成**词级时间戳（或者 VAD 把
语音滤掉了、words.json 只有几个词），cutfit 就会静默跳过，切点还是 OCR 的原值，
于是「末尾多带后一句的几个词」照旧。

补好 words.json 之后，用这个工具把这批课的切点重算一遍即可，不必重跑整条
流水线（文本已经校对过，重跑反而有回归风险）。

用法:
  python tools/refit_cuts.py 17 19 20 21 23 25 02        # 只报告
  python tools/refit_cuts.py 17 19 20 21 23 25 02 --write # 写回 lesson JSON
  python tools/refit_cuts.py --write                      # 全系列
"""
import io, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cutfit                                                   # noqa: E402

ROOT = cutfit.ROOT
TAG = re.compile(r"<[^>]+>")


def refit(f, write=False):
    p = os.path.join(ROOT, "tools", "lessons", f)
    d = json.load(io.open(p, encoding="utf-8"))
    n = f[:2]
    segs = [b for b in d.get("part2") or [] if b.get("type") != "day"]
    texts = [TAG.sub("", b.get("en", "")).strip() for b in segs]
    base, src = d["cuts"], "当前 cuts"
    pc = cutfit.ocr_cuts(f)                    # 精修前的原始 OCR 切点（有就用它当基准）
    if pc and len(pc) == len(d["cuts"]):
        base, src = pc, "work_seg/%s.precut.json" % n
    new, info = cutfit.refine(n, texts, base, d.get("dur"))
    rows = []
    for seg, (oa, ob), (na, nb), it in zip(segs, base, new, info):
        rows.append((seg["no"], oa, ob, na, nb, nb - ob, it[0]))
    print("=" * 74)
    print("%s   基准=%s   %d 段" % (f[:-5], src, len(base)))
    for no, oa, ob, na, nb, db, cov in rows:
        if abs(db) > 0.02 or abs(na - oa) > 0.02:
            print("   seg%s  %.2f-%.2f -> %.2f-%.2f   b%+.2f  (覆盖 %.0f%%)"
                  % (no, oa, ob, na, nb, db, 100 * (cov or 0)))
    # 与现有 cuts 的真实差异（写回后页面/音频会变成 new）
    diff = max((abs(a - c[0]) + abs(b - c[1]) for (a, b), c in zip(new, d["cuts"])), default=0)
    print("   与现有 cuts 的最大差异 %.2fs；本次会改 %d 段"
          % (diff, sum(1 for (a, b), c in zip(new, d["cuts"]) if abs(a - c[0]) > 0.02 or abs(b - c[1]) > 0.02)))
    if write:
        d["cuts"] = new
        io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
        print("   已写回 %s" % p)
    return new


def main():
    argv = list(sys.argv[1:])
    write = "--write" in argv
    picks = {a for a in argv if not a.startswith("--")}
    for f in sorted(os.listdir(os.path.join(ROOT, "tools", "lessons"))):
        if not f.endswith(".json"):
            continue
        if picks and f[:2] not in picks:
            continue
        refit(f, write)


if __name__ == "__main__":
    main()
