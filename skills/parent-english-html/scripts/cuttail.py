# -*- coding: utf-8 -*-
"""用**整片词级时间戳**量每段切点「头尾各多带/少了几个词」。

为什么不用 segcheck 的孤立片段重听
----------------------------------
`segcheck.py` 把 segNN.mp3 单独喂给 whisper —— 片段短、没有上下文，尾部
静音上极易**幻觉**（02/01 就凭空冒出 "Always remember to check out our
website for more information. www.cdc.gov.uk kitchen kitchen…"）。所以它只
适合做「粗筛」，不适合定量。

这里换个思路，全部基于 `work_prep/NN/words.json`（整片转写、词级时间）：
  1. 把整课文本词序列和整片词序列做一次全局对齐（复用 cutfit.align）；
  2. 于是每个段落的**首词 / 末词**有了真实时刻 `t_start` / `t_end`；
  3. 三种毛病分别量：
       尾多带 = (t_end, b] 区间里还完整开始了几个词
       头多带 = [a, t_start) 区间里还完整结束了几个词
       被切短 = t_end 超过 b（末词还没说完就切了）

用法:
  python tools/cuttail.py              # 全系列汇总
  python tools/cuttail.py 02 14 19     # 只看某几课（明细）
  python tools/cuttail.py --list       # 额外列出所有有问题的 (课,段)
  python tools/cuttail.py --base       # 拿 work_seg/NN.precut.json 当切点（看精修前）
"""
import io, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cutfit                                                    # noqa: E402

ROOT = cutfit.ROOT
TAG = re.compile(r"<[^>]+>")
TAIL_OK = 0.35          # 末词说完后再留这么久，不算多带
HEAD_OK = 0.45          # 首词开始前留这么久，不算多带
SHORT_OK = 0.20         # 末词超出 b 这么久才算「被切短」


def load(f):
    d = json.load(io.open(os.path.join(ROOT, "tools", "lessons", f), encoding="utf-8"))
    segs = [b for b in d.get("part2") or [] if b.get("type") != "day"]
    return d, segs


def measure(n, texts, cuts):
    """-> [(t_start, t_end, a, b, 尾多带词表, 头多带词表)]
    无法对齐的段 t_start/t_end 返回 None
    """
    A = [cutfit.key(w) for t in texts for w in t.split()]
    spans, k = [], 0
    for t in texts:
        w = t.split()
        spans.append((k, k + len(w)))
        k += len(w)
    idx = cutfit.index(n)
    if not idx or not A:
        return [(None, None, a, b, [], []) for a, b in cuts]
    pairs = cutfit.align(A, [w[1] for w in idx])
    if not pairs:
        return [(None, None, a, b, [], []) for a, b in cuts]
    m = dict(pairs)
    out = []
    for (s, e), (a, b) in zip(spans, cuts):
        hit = [m[i] for i in range(s, e) if i in m]
        if len(hit) < max(2, cutfit.MIN_COV * (e - s)):
            out.append((None, None, a, b, [], []))
            continue
        j0, j1 = min(hit), max(hit)
        t_start = idx[j0][0]
        t_end = idx[j1][0] + idx[j1][2]
        extra = [(round(idx[j][0], 2), idx[j][1])
                 for j in range(j1 + 1, len(idx))
                 if t_end + TAIL_OK < idx[j][0] < b]
        head = [(round(idx[j][0], 2), idx[j][1])
                for j in range(j0 - 1, -1, -1)
                if idx[j][0] + idx[j][2] > a and idx[j][0] + idx[j][2] < t_start - HEAD_OK]
        out.append((round(t_start, 2), round(t_end, 2), a, b, extra, head))
    return out


def main():
    argv = list(sys.argv[1:])
    base = "--base" in argv
    show_list = "--list" in argv
    picks = {a for a in argv if not a.startswith("--")}
    tot = ok = unk_all = 0
    bad = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools", "lessons"))):
        if not f.endswith(".json"):
            continue
        n = f[:2]
        if picks and n not in picks:
            continue
        d, segs = load(f)
        texts = [TAG.sub("", b.get("en", "")).strip() for b in segs]
        cuts = d["cuts"]
        if base:
            p = os.path.join(ROOT, "work_seg", "%s.precut.json" % n)
            if os.path.exists(p):
                c2 = json.load(io.open(p, encoding="utf-8")).get("cuts")
                if c2 and len(c2) == len(cuts):
                    cuts = c2
        res = measure(n, texts, cuts)
        unk = 0
        for seg, (ts, te, a, b, extra, head) in zip(segs, res):
            tot += 1
            if te is None:
                unk += 1
                unk_all += 1
                continue
            short = te > b + SHORT_OK
            if not extra and not head and not short:
                ok += 1
            else:
                bad.append((f[:-5], seg["no"], len(extra), len(head), short, a, b, ts, te,
                            " ".join(w for _t, w in extra[:6]),
                            " ".join(w for _t, w in head[:6])))
        if picks:
            print("=" * 74)
            print(f[:-5], "  无法对齐 %d 段" % unk)
            for seg, (ts, te, a, b, extra, head) in zip(segs, res):
                if te is None:
                    print("  seg%s  ？？  a=%.2f b=%.2f" % (seg["no"], a, b))
                else:
                    print("  seg%s  [%.2f,%.2f]  实说[%.2f,%.2f]  尾多带 %d %s%s"
                          % (seg["no"], a, b, ts, te, len(extra),
                             " ".join(w for _t, w in extra[:6]),
                             "   头多带 %d %s" % (len(head), " ".join(w for _t, w in head[:5]))
                             if head else ""))
    print("\n---- 汇总 (%s) ----" % ("precut" if base else "current"))
    okn = [x for x in bad if x[2] == 0 and x[3] == 0 and not x[4]]
    print("总 %d 段；无法对齐 %d 段；可判定 %d 段 -> 干净 %d 段 (%.0f%%)，有问题 %d 段"
          % (tot, unk_all, tot - unk_all, ok, 100.0 * ok / max(tot - unk_all, 1), len(bad)))
    if show_list:
        for x in sorted(bad, key=lambda z: -(z[2] * 2 + z[3])):
            tag = []
            if x[2]:
                tag.append("尾多%d(%s)" % (x[2], x[9]))
            if x[3]:
                tag.append("头多%d(%s)" % (x[3], x[10]))
            if x[4]:
                tag.append("被切短")
            print("   %-28s seg%-3s %s" % (x[0], x[1], "  ".join(tag)))


if __name__ == "__main__":
    main()
