# -*- coding: utf-8 -*-
"""深一层验收：音频时长是否覆盖字幕区间 + 中文高亮覆盖率。

  python tools/verify_deep.py           # 全量
  python tools/verify_deep.py 05 19     # 指定几课

比 verify_review.py 更严：
  ① 每个 segNN.mp3 的实际时长要 ≈ cuts 里的 (b-a)，偏差 >0.4s 说明切歪了
     （用户反馈「分段听力被分割得不完整」就是这类问题）
  ② 按「段」和按「词」两个口径统计中文高亮覆盖率
"""
import io, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "亲子英语")
LES = os.path.join(ROOT, "tools", "lessons")
CJK = re.compile(r"[\u4e00-\u9fff]")


def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", p], capture_output=True, text=True)
    try:
        return float(o.stdout.strip())
    except Exception:
        return None


def check(n, slug):
    ljp = os.path.join(LES, slug + ".json")
    cuts = None
    if os.path.exists(ljp):
        cuts = json.load(io.open(ljp, encoding="utf-8"))["cuts"]
    else:
        # 01-newborn-morning 是早期手工页，没有 lesson.json；它的切点落在
        # work_seg/NN.cuts.json（由 tools/_fix01_legacy.py 生成）。
        alt = os.path.join(ROOT, "work_seg", "%s.cuts.json" % n)
        if os.path.exists(alt):
            cuts = json.load(io.open(alt, encoding="utf-8"))["cuts"]
    if not cuts:
        return None
    aud = os.path.join(OUT, slug, "audio")
    bad, miss = [], []
    for i, (a, b) in enumerate(cuts, 1):
        p = os.path.join(aud, "seg%02d.mp3" % i)
        if not os.path.isfile(p):
            miss.append(i)
            continue
        d = dur(p)
        want = b - a
        if d is None or abs(d - want) > 0.40:
            bad.append((i, a, b, want, d))
    # 中文高亮覆盖
    h = io.open(os.path.join(OUT, slug, "index.html"), encoding="utf-8").read()
    en_spans, cn_spans = [], 0
    for m in re.finditer(r'<div class="en"[^>]*>(.*?)</div>\s*<div class="cn">(.*?)</div>',
                         h, re.S):
        en, cn = m.group(1), m.group(2)
        # 英文 span 是手写的，引号可能单可能双
        keys = [x for x in re.findall(r"""<span\s+class=['"]k\s*[a-z]?['"]\s+title=['"]([^'"]*)['"]""", en)
                if CJK.search(x)]
        en_spans.extend(keys)
        cn_spans += len(re.findall(r'<span class="k\s*[a-z]?">', cn))
    seg_n = len(re.findall(r'<div class="seg">', h))
    cov_seg = (cn_spans / len(en_spans) * 100) if en_spans else 0.0
    return {"n": n, "slug": slug, "cuts": len(cuts), "miss": miss, "bad": bad,
            "en_keys": len(en_spans), "cn_keys": cn_spans, "cov": cov_seg,
            "segs": seg_n, "cn_div": h.count('<div class="cn">')}


def main():
    picks = sys.argv[1:]
    slugs = sorted(d for d in os.listdir(OUT)
                   if os.path.isdir(os.path.join(OUT, d)) and re.match(r"\d\d-", d))
    if picks:
        slugs = [s for s in slugs if s[:2] in picks]
    tot_k = tot_c = 0
    low = []
    for s in slugs:
        try:
            r = check(s[:2], s)
        except Exception as e:
            print("!! %s %s" % (s, e))
            continue
        if r is None:
            print("%-26s (手工页，无 lesson.json，跳过音频核对)" % s)
            continue
        tot_k += r["en_keys"]
        tot_c += r["cn_keys"]
        flags = []
        if r["miss"]:
            flags.append("缺音频 %s" % r["miss"])
        if r["bad"]:
            flags.append("时长不符 %d 条" % len(r["bad"]))
        if r["segs"] != r["cn_div"]:
            flags.append("seg %d != cn %d" % (r["segs"], r["cn_div"]))
        print("%-26s cuts=%-3d seg=%-3d 高亮 en=%-4d cn=%-4d %5.1f%%  %s"
              % (s, r["cuts"], r["segs"], r["en_keys"], r["cn_keys"], r["cov"],
                 "；".join(flags) or "OK"))
        for b in r["bad"][:3]:
            print("      seg%02d  切点 %.2f-%.2f (%.2fs) 实际 %.2fs" % b)
        if r["cov"] < 60:
            low.append(s)
    print("-" * 78)
    print("合计 %d 课；按词覆盖率 %.1f%%" % (len(slugs), tot_c / tot_k * 100 if tot_k else 0))
    if low:
        print("覆盖率 <60%% 的课：%s" % " ".join(low))


if __name__ == "__main__":
    main()
