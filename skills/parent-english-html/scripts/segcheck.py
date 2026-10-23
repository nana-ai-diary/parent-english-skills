# -*- coding: utf-8 -*-
"""批量体检：把每个 segNN.mp3 重新听一遍，和该段应有的文本比对，
量出「末尾多出来的词 / 开头多出来的词」。

这是「分段音频末尾多出后一句几个词」这件事的唯一可信判据 ——
cuts 的数字对不对，只有把音频真的听一遍才知道。

用法:
  python tools/segcheck.py                 # 全系列，输出 TSV + 汇总
  python tools/segcheck.py 08 29           # 只看某几课（课号）
  python tools/segcheck.py --tag before    # 结果写到 _segcheck_<tag>.tsv
"""
import io, json, os, re, sys, time
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "outputs", "亲子英语")
TAG = re.compile(r"<[^>]+>")
WORD = re.compile(r"[^a-z0-9']+")        # 注意：匹配「非」词字符，sub 掉它

_m = None


def model():
    global _m
    if _m is None:
        from faster_whisper import WhisperModel
        _m = WhisperModel("small", device="cpu", compute_type="int8")
    return _m


def key(w):
    """词 -> 比对用的键；纯标点 token 返回空串（会被丢掉，不参与比对）"""
    return WORD.sub("", w.lower())


def words_of(s):
    return [k for k in (key(x) for x in s.split()) if k]


def unroll(ws, run_max=3):
    """把「同一个词连续重复 ≥run_max 次」的幻觉段截断（whisper 在长静音/音乐上会复读）"""
    out, i = [], 0
    while i < len(ws):
        j = i
        while j < len(ws) and ws[j] == ws[i]:
            j += 1
        if j - i >= run_max:
            out.append(ws[i])
            return out                      # 复读一开始，后面就不可信了
        out.extend(ws[i:j])
        i = j
    return out


def plain(s):
    return TAG.sub("", s)


def _sim(a, b):
    if a == b:
        return 1.0
    if not a or not b or a[:1] != b[:1] or abs(len(a) - len(b)) > 2:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _anchor(ww, wg, tail=True, maxl=10):
    """want 末尾（或开头）连续 L 个词在 got 里的落点 -> (下标, L)

    用「最长连续后缀匹配」而不是「第 N 个匹配块」—— ASR 常在句子中间多听出
    一个词（Square. / Oh yeah），按匹配块取会把后半句全算成「多余」。这里只认
    连续匹配，中间插字也不影响锚点。
    找不到（L<3）就返回 None，表示这一段无法判断，不计入统计。
    """
    if len(ww) < 3 or len(wg) < 3:
        return None, 0
    for L in range(min(maxl, len(ww), len(wg)), 2, -1):
        pat = ww[-L:] if tail else ww[:L]
        rng = range(len(wg) - L, -1, -1) if tail else range(0, len(wg) - L + 1)
        for p in rng:
            if all(_sim(pat[i], wg[p + i]) >= 0.82 for i in range(L)):
                return (p + L if tail else p), L
    return None, 0


def check(want, got):
    """-> (tail_extra, head_extra, n_match)；无法判断时 tail 返回 None"""
    ww = words_of(want)
    wg = unroll(words_of(got))
    if not ww or not wg:
        return None, [], 0
    nm = sum(b.size for b in SequenceMatcher(None, ww, wg).get_matching_blocks())
    a_t, L = _anchor(ww, wg, tail=True)
    if a_t is None:
        return None, [], nm
    a_h, _ = _anchor(ww, wg, tail=False)
    tail = wg[a_t:]
    head = wg[:a_h] if a_h is not None else []
    return tail, head, nm


def main():
    argv = list(sys.argv[1:])
    tag = "out"
    if "--tag" in argv:                      # --tag 后面跟的是值，不算课号
        i = argv.index("--tag")
        tag = argv[i + 1] if i + 1 < len(argv) else "out"
        del argv[i:i + 2]
    only = None
    if "--pairs" in argv:                    # 只查指定 (slug, segno) 清单，省时间
        i = argv.index("--pairs")
        pf = argv[i + 1]
        del argv[i:i + 2]
        if not os.path.isabs(pf):
            pf = os.path.join(ROOT, pf)
        only = set()
        for line in io.open(pf, encoding="utf-8"):
            c = line.rstrip("\n").split("\t")
            if len(c) >= 2 and c[0] and c[1]:
                only.add((c[0], c[1]))
    root = OUT
    if "--dir" in argv:                      # 查另一份音频（before/after 对比用）
        i = argv.index("--dir")
        root = argv[i + 1]
        del argv[i:i + 2]
        if not os.path.isabs(root):
            root = os.path.join(ROOT, root)
    args = [a for a in argv if not a.startswith("--")]
    picks = set(args)
    rows, t0 = [], time.time()
    for slug in sorted(os.listdir(root)):
        if not slug[:2].isdigit():
            continue
        if picks and slug[:2] not in picks:
            continue
        lj = os.path.join(ROOT, "tools", "lessons", slug + ".json")
        if not os.path.exists(lj):
            continue
        d = json.load(io.open(lj, encoding="utf-8"))
        segs = [b for b in d["part2"] if b.get("type") != "day"]
        aud = os.path.join(root, slug, "audio")
        if not os.path.isdir(aud):
            aud = os.path.join(root, slug)
        for seg in segs:
            if only is not None and (slug, seg["no"]) not in only:
                continue
            p = os.path.join(aud, "seg%s.mp3" % seg["no"])
            if not os.path.exists(p):
                continue
            try:
                ss, info = model().transcribe(p, beam_size=1, temperature=0,
                                              condition_on_previous_text=False,
                                              language="en")
                got = " ".join(x.text.strip() for x in ss)
            except Exception as e:                      # noqa: BLE001
                rows.append((slug, seg["no"], -1, 0, 99, 99, "", "ERR %s" % e))
                continue
            want = plain(seg["en"]).strip()
            tail, head, nm = check(want, got)
            nt = -1 if tail is None else len(tail)
            rows.append((slug, seg["no"], round(info.duration, 2), nm,
                         nt, len(head), " ".join((tail or [])[:6]), want[:40]))
            print("%-26s seg%s dur=%5.2f match=%2d 尾+%s 头+%d | %s"
                  % (slug, seg["no"], info.duration, nm,
                     "?" if nt < 0 else nt, len(head),
                     " ".join((tail or [])[:6])), flush=True)
    path = os.path.join(ROOT, "_segcheck_%s.tsv" % tag)
    with io.open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write("\t".join(str(x) for x in r) + "\n")
    ok_n = [r for r in rows if r[4] == 0]
    one = [r for r in rows if r[4] == 1]
    bad = [r for r in rows if r[4] >= 2]
    unk = [r for r in rows if r[4] < 0]
    print("\n---- 汇总 (%s) ----" % tag)
    print("段数 %d；正常(尾+0) %d 段 (%.0f%%)；多 1 词 %d 段；多 ≥2 词 %d 段；无法判断 %d 段；耗时 %.1f 分"
          % (len(rows), len(ok_n), 100.0 * len(ok_n) / max(len(rows), 1),
             len(one), len(bad), len(unk), (time.time() - t0) / 60))
    print("结果写入 %s" % path)


if __name__ == "__main__":
    main()
