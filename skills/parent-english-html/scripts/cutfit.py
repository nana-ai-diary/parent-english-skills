# -*- coding: utf-8 -*-
"""用「整课文本 ↔ 转录词序列」的全局对齐来校准分段切点。

问题
----
分段终点最早是这样来的：

    b = 下一条字幕出现时间 + 0.15     # = work_ocr/NN.jsonl 里的帧时间

而 OCR 抽帧是 **1 秒 1 帧**，`rt` 只有整秒精度；烧录字幕又总比语音早出现
一点点。两者叠加 → 切点系统性偏晚最多 1 秒，**每段音频末尾都会多带出
后一句的头几个词**（用户反馈「几乎每句都这样」）。

做法
----
整课的文本（每段 en 按顺序拼起来）与整篇转录的词序列**说的是同一段话**，
所以做一次全局单调对齐（Needleman–Wunsch），就能给出**每个词**的
（插值）时间。于是：

    a = 本段第一个词的时刻 - PAD_HEAD
    b = 本段最后一个词的时刻 + 一个词长，再和「下一个词开始前的中点」取小

取中点这一步是关键：有没有停顿都能落在一个无偏的位置 ——
连读时中点≈真实边界，有停顿时中点落在静音里（无害）。
再叠一层护栏：`b` 不许比旧值早超过 MAX_TRIM 秒，防止转录漏词把整段切残。

用法:
  python tools/cutfit.py --stat        # 体检：逐段给出 旧 a,b / 新 a,b
  python tools/cutfit.py 05 02 --diff  # 只看某几课的明细
"""
import io, json, os, re, statistics, sys
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r"<[^>]+>")
WORD = re.compile(r"[^a-z0-9']+")            # 注意：匹配「非」词字符，sub 掉它
NER = re.compile(r"\[[^\]]*\]|\([^)]*\)")

PAD_HEAD = 0.30         # 起音前留一点，避免把第一个词的起音切掉
TAIL = 0.12             # 末词说完后再留一点
MID_SHARE = 0.50        # 与下一个词之间的中点
MIN_LEN = 0.60
MIN_COV = 0.45          # 本段词能对上转录的比例，太低就不动

# 尾部最多提前多少秒（护栏，防转录漏词把整段切残）。
# 按「本段对齐覆盖率」分档：对得越准，越可以放心地按词级时间收。
MAX_TRIM_BY_COV = ((0.80, 3.00), (0.60, 1.90), (0.00, 1.30))
MAX_TRIM = MAX_TRIM_BY_COV[-1][1]        # 供体检/工具引用（最保守那档）


def max_trim(cov):
    for c, v in MAX_TRIM_BY_COV:
        if cov >= c:
            return v
    return MAX_TRIM

MATCH, NEAR, MIS, GAP = 1.0, 0.45, -1.0, -0.65


def key(w):
    """词 -> 比对用的键（去标点小写；纯标点 token 原样保留，保证词位一一对应）"""
    return WORD.sub("", w.lower()) or w.lower()


# ---------------- 转录 ----------------
def _dedup_repeats(raw, min_reps=3):
    """片尾复读护栏。raw = [(start, end, key)]（还**没**做过时长下限钳位）。

    whisper 遇到长静音会复读：同一句话连出十几遍，且每一遍的时间戳被压成
    同一个时刻（时长 ≈ 0）。这些复读会让**全局对齐的锚点被拖到最后一遍** ——
    最后一段的 `t_end` 就被拉到片尾，切点跟着变晚，音频里多出整句。

    判据（两条同时满足才剪）：
      1. 某个 n 元组（n≥4）连续重复 ≥3 次；
      2. 这个重复块里 ≥60% 的词时长 ≤0.02 秒（真语音不可能整块零时长）。
    命中就把第一个重复块**整块连同后面**剪掉 —— 真正那句话在更早的位置。
    """
    n_words = len(raw)
    for i in range(n_words):
        for n in (10, 8, 6, 5, 4):
            if i + n * min_reps > n_words:
                continue
            pat = [r[2] for r in raw[i:i + n]]
            reps = 1
            while (i + (reps + 1) * n <= n_words
                   and [r[2] for r in raw[i + reps * n:i + (reps + 1) * n]] == pat):
                reps += 1
            if reps < min_reps:
                continue
            blk = raw[i:i + reps * n]
            if sum(1 for r in blk if r[1] - r[0] <= 0.02) >= 0.6 * len(blk):
                return raw[:i]
    return raw


def index(n):
    """-> [(t, key, step)]：整篇转录摊平成「词 + 时间 + 该词时长」

    优先用 `work_prep/NN/words.json`（whisper `word_timestamps=True` 的**真**词级时间，
    由 `tools/wordtime.py` 生成）；没有才退回「段级时间 + 段内按词数均分」的插值 ——
    插值在 4~5 秒的分段里误差约 0.3 秒，会让切点差半个词。
    """
    wp = os.path.join(ROOT, "work_prep", n, "words.json")
    if os.path.exists(wp):
        try:
            raw = []
            for w in json.load(io.open(wp, encoding="utf-8")):
                k = key(w.get("word", ""))
                if not k:
                    continue
                raw.append((float(w["start"]), float(w["end"]), k))
            if raw:
                raw = _dedup_repeats(raw)
                return [(s, k, max(0.05, e - s)) for s, e, k in raw]
        except Exception:                               # noqa: BLE001
            pass
    p = os.path.join(ROOT, "work_prep", n, "transcript.json")
    if not os.path.exists(p):
        return []
    try:
        segs = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return []
    out = []
    for sg in segs:
        ws = NER.sub("", sg.get("text", "")).split()
        if not ws:
            continue
        span = max(sg["end"] - sg["start"], 0.01)
        step = span / len(ws)
        for j, w in enumerate(ws):
            out.append((sg["start"] + step * j, key(w), step))
    return out


# ---------------- 全局对齐 ----------------
def _sim(a, b):
    if a == b:
        return MATCH
    if not a or not b:
        return MIS
    if abs(len(a) - len(b)) > 3 or a[:1] != b[:1]:
        return MIS
    if a in b or b in a:
        return NEAR
    return NEAR if SequenceMatcher(None, a, b).ratio() >= 0.72 else MIS


def align(A, B):
    """A（整课文本词）↔ B（转录词）的全局单调对齐 -> [(i, j)] 匹配对"""
    n, m = len(A), len(B)
    if not n or not m:
        return []
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bk = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + GAP
        bk[i][0] = 1
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + GAP
        bk[0][j] = 2
    for i in range(1, n + 1):
        ai = A[i - 1]
        pr, pc, pb = dp[i - 1], dp[i], bk[i]
        for j in range(1, m + 1):
            bj = B[j - 1]
            sc = _sim(ai, bj)
            if sc == MIS and (abs(len(ai) - len(bj)) > 3 or ai[:1] != bj[:1]):
                sc = MIS
            best = pr[j - 1] + (sc if sc > 0 else MIS)
            k = 0
            up = pr[j] + GAP
            if up > best + 1e-9:
                best, k = up, 1
            left = pc[j - 1] + GAP
            if left > best + 1e-9:
                best, k = left, 2
            pc[j] = best
            pb[j] = k
    pairs, i, j = [], n, m
    while i > 0 and j > 0:
        k = bk[i][j]
        if k == 0:
            if _sim(A[i - 1], B[j - 1]) > 0:
                pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def overrides():
    """手写切点覆盖 tools/cutsfix.json = {"<课号>": {"<段号>": [a, b]}}

    自动层判不出来 / 判错时的最后一招（和 `tools/goals.json`、`tools/p2/`、
    `tools/cn/` 是同一套路：机器负责 99%，人负责剩下那 1% 并留下理由）。
    例：24 课末段的视频里说了两遍 "good job"，页面文本只有一遍 —— 自动层
    因为段末词没全对上而不敢收尾，就用手写值把 `b` 钉在第一个 "job" 之后。
    """
    p = os.path.join(ROOT, "tools", "cutsfix.json")
    if not os.path.exists(p):
        return {}
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return {}
    out = {}
    for n, segs in d.items():
        if n.startswith("_"):
            continue
        for no, ab in (segs or {}).items():
            out[(str(n), str(no))] = [float(ab[0]), float(ab[1])]
    return out


def refine(n, texts, cuts, dur=None):
    """texts: 每段的纯文本（与 cuts 一一对应）-> 新的 cuts

    两趟：先定**头**（`a`），再定**尾**（`b`）—— 因为尾部的「不许越过下一段
    开头」这条约束要用到下一段已经算好的 `a`。

    尾部护栏不再拍脑袋写死秒数，而是看**语义证据**：
      * 本段末尾的词有没有对上转录（`miss_tail`）—— 没对上就别信 `t_end`，
        只按覆盖率给一个保守的回收量；
      * 对上了就可以放心地按词级时间收（甚至**回补**：见下）。

    「回补」是必须的：OCR 抽帧只有整秒精度，有时会把一段的终点定得过早，
    于是页面文本比音频长（07 课把整首字母歌写进了一段 3.5 秒的音频）。
    这时 `t_end` 明显晚于 `b_old`，只要本段末尾的词都对上了，就允许把 `b`
    往后放到「下一个词的起点之前」—— 上界用下一段精修后的 `a` 来卡，不会串段。

    返回 (newcuts, info)；info 里是每段的 (覆盖率, 旧a, 旧b, 新a, 新b, 覆盖率)。
    """
    A = [key(w) for t in texts for w in t.split()]   # 展平成一整条（与 spans 同长）
    spans, k = [], 0
    for t in texts:
        w = t.split()
        spans.append((k, k + len(w)))
        k += len(w)
    idx = index(n)
    if not idx or not A:
        return [list(c) for c in cuts], []
    pairs = align(A, [w[1] for w in idx])
    if not pairs:
        return [list(c) for c in cuts], []
    m = {}
    for i, j in pairs:
        m[i] = j

    # ---- 第一趟：收集证据 + 定头 ----
    ev = [None] * len(cuts)
    a_new = [None] * len(cuts)
    for si, ((s, e), (a_old, b_old)) in enumerate(zip(spans, cuts)):
        hit = [m[i] for i in range(s, e) if i in m]
        cov = len(hit) / max(e - s, 1)
        if len(hit) < max(2, MIN_COV * (e - s)):
            a_new[si] = a_old
            continue
        j0, j1 = min(hit), max(hit)
        ev[si] = dict(cov=cov, j0=j0, j1=j1,
                      t0=idx[j0][0],
                      t_end=idx[j1][0] + idx[j1][2],
                      t_next=(idx[j1 + 1][0] if j1 + 1 < len(idx) else None),
                      miss_tail=(e - 1) - j1,
                      a_old=a_old, b_old=b_old)
        t_prev_end = (idx[j0 - 1][0] + idx[j0 - 1][2]) if j0 > 0 else 0.0
        a = max(idx[j0][0] - PAD_HEAD, t_prev_end + 0.02, 0.0)
        a = min(a, idx[j0][0])              # 不越过本段首词
        a = max(a, a_old - 0.25)            # 不许比原来早太多（防抖）
        a_new[si] = a

    # ---- 第二趟：定尾 ----
    out, info = [], []
    for si in range(len(cuts)):
        a_old, b_old = cuts[si]
        d = ev[si]
        if d is None:
            out.append([a_old, b_old])
            info.append((None, a_old, b_old, a_old, b_old, 0.0))
            continue
        a = a_new[si]
        t_end, t_next = d["t_end"], d["t_next"]
        gap = max((t_next - t_end) if t_next is not None else 0.30, 0.0)
        # 尾部：末词说完 + 一点，但不越过与下一个词的中点
        b = min(t_end + TAIL, t_end + MID_SHARE * gap)
        if d["miss_tail"] > 1 or d["cov"] < 0.60:
            b = max(b, b_old - max_trim(d["cov"]))      # 末尾没对上 -> 保守回收
        elif b > b_old and si + 1 < len(cuts) and a_new[si + 1] is not None:
            b = min(b, max(a_new[si + 1] - 0.05, b_old))  # 回补：卡在下一段开头前
        if b - a < MIN_LEN:
            b = a + MIN_LEN
        if dur:
            b = min(b, dur)
        if b <= a:
            a, b = a_old, b_old
        out.append([round(a, 2), round(b, 2)])
        info.append((d["cov"], a_old, b_old, round(a, 2), round(b, 2), d["cov"]))

    # ---- 最后一招：手写覆盖 ----
    ov = overrides()
    nk = str(n).zfill(2)
    for i in range(len(out)):
        hit = ov.get((nk, "%02d" % (i + 1)))
        if hit:
            out[i] = [round(hit[0], 2), round(hit[1], 2)]
    return out, info


# ---------------- 体检 ----------------
def lesson(f):
    d = json.load(io.open(os.path.join(ROOT, "tools", "lessons", f), encoding="utf-8"))
    segs = [b for b in d.get("part2") or [] if b.get("type") != "day"]
    return d, segs, [TAG.sub("", b.get("en", "")).strip() for b in segs]


def ocr_cuts(f):
    """精修**之前**的切点（纯 OCR 帧时间推算的那份，apply_p2 会落盘）

    `--stat` 要拿它当基准；拿「已经精修过的 cuts」当基准只会看到归零，
    看不出这一整轮到底把尾巴收掉了多少。
    """
    p = os.path.join(ROOT, "work_seg", "%s.precut.json" % f[:2])
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8")).get("cuts")
    except Exception:                                   # noqa: BLE001
        return None


def main():
    picks = {a for a in sys.argv[1:] if not a.startswith("--")}
    verbose = "--diff" in sys.argv
    rows = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools", "lessons"))):
        if not f.endswith(".json"):
            continue
        n = f[:2]
        if picks and n not in picks:
            continue
        d, segs, texts = lesson(f)
        if not os.path.exists(os.path.join(ROOT, "work_prep", n, "transcript.json")) \
                and not os.path.exists(os.path.join(ROOT, "work_prep", n, "words.json")):
            print("跳过 %s（无转录）" % f)
            continue
        base = ocr_cuts(f) if (ocr_cuts(f) and len(ocr_cuts(f)) == len(d["cuts"])) else d["cuts"]
        new, info = refine(n, texts, base, d.get("dur"))
        if verbose:
            print("=" * 74)
            print(f[:-5])
        for (seg, (oa, ob), (na, nb), it) in zip(segs, base, new, info):
            rows.append((f[:-5], seg["no"], ob - nb))
            if verbose:
                print("  %s  %.2f-%.2f -> %.2f-%.2f   b-%+.2f" %
                      (seg["no"], oa, ob, na, nb, nb - ob))
    deltas = sorted(x for _s, _n, x in rows)
    moved = [x for x in deltas if abs(x) > 0.02]
    print("\n段数 %d；会改的 %d (%d%%)" % (len(rows), len(moved), round(100 * len(moved) / max(len(rows), 1))))
    if deltas:
        print("尾部缩短量 (基准 b - 精修 b): 中位 %+.2f 均值 %+.2f 最小 %+.2f 最大 %+.2f"
              % (statistics.median(deltas), statistics.mean(deltas), deltas[0], deltas[-1]))
        print("没被缩短的段: %d / %d" % (len([x for x in deltas if x <= 0.02]), len(deltas)))


if __name__ == "__main__":
    main()
