# -*- coding: utf-8 -*-
"""把烧录字幕 OCR 结果变成「逐句精听」的分段骨架。

用法:
  python tools/reseg.py 20            # 读 work_ocr/20.jsonl -> 写 work_seg/20.json，并打印行清单

产出的 work_seg/<n>.json:
  {"n":"20","dur":104.07,"cuts":[[a,b],...],
   "segs":[{"no":"01","en":"...","cn":"...","t":1.0}, ...]}

后续由 tools/merge_p2.py 把「我手写的 en 高亮 + cn 译文」合并回 lessons/<slug>.json。
"""
import difflib, io, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enfix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CJK = re.compile(r"[\u4e00-\u9fff]")


def norm(s):
    """只留字母数字，用于「同一句」的判重"""
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

# 片尾水印/关注引导、纯中文标题卡、角标 logo —— 都不进逐句精听
DROP = re.compile(r"点赞|关注|找戎|小粽粽|订阅|字幕|字幕组|@|转发|评论区"
                  r"|toysreview|ryantoys|ryantoy|TOVSREVIE"
                  r"|mnopqr|hijklm|defghij|bcdefg|FGHIJK")


def is_noise(part):
    """画面角标水印（TOYS REVIEW 被 OCR 读成 TOVS REVIEN / OVSREUIEI / 光FRIe…）

    特征：很短、几乎全大写字母。整条水印会被切成独立的一段，
    必须在「分中/英」之前剔掉，否则它会拼进英文行、导致相邻帧去重失效。
    """
    s = part.strip()
    if not s:
        return True
    core = re.sub(r"[^A-Za-z]", "", s)
    if len(core) < 4:
        return False
    if sum(c.isupper() for c in core) / len(core) >= 0.75 and len(re.sub(r"\s+", "", s)) <= 18:
        return True
    # 水印常把某个字母读成中文（光FRIe / 找戎）——残留 CJK 且英文很少
    if CJK.search(s) and len(re.sub(r"\s+", "", s)) <= 12 and 3 <= len(core) <= 10 \
            and sum(c.isupper() for c in core) / len(core) >= 0.5:
        return True
    return False

PAD_HEAD = 0.35     # 每段往前多切一点，避免起音被切掉
PAD_TAIL = 0.05     # 到下一句字幕出现前收尾


def probe_dur(src):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", src], capture_output=True, text=True)
    try:
        return round(float(out.stdout.strip()), 2)
    except Exception:
        return None


_LEX = None


def lex():
    """断词 / 纠错共用的词典。

    **不收 tools/lessons/*.json**：那是 OCR 回写的产物，收进来会把 OCR
    错字洗成合法词，repair 就再也纠不动了（自污染闭环）。
    """
    global _LEX
    if _LEX is None:
        _LEX = enfix.build_lexicon(lessons=False)
    return _LEX


def load_lines(n):
    p = os.path.join(ROOT, "work_ocr", "%s.jsonl" % n)
    rows = [json.loads(l) for l in io.open(p, encoding="utf-8") if l.strip()]
    L = lex()
    out = []
    for r in rows:
        parts = [x.strip() for x in r["txt"].split("|")]
        parts = [p for p in parts if not is_noise(p)]
        en = " ".join(p for p in parts if p and not CJK.search(p)).strip()
        cn = "".join(p for p in parts if p and CJK.search(p)).strip()
        if not en:                       # 纯中文（标题卡 / 水印）跳过
            continue
        if DROP.search(en) or DROP.search(cn):
            continue
        en = enfix.fix_line(en, L)       # 修 OCR 连写：Washyourhands -> Wash your hands
        out.append({"t": float(r["t"]), "en": en, "cn": cn})
    return out


def dedup(out):
    """去掉与上一行重复的英文（OCR 抖动 / 同一 cue 被连读多帧）

    归一化掉标点与大小写，再做「包含」合并（同一句被读全/读残）。
    **必须放在 repair 之后**：修复会把相邻几行统一成转录的写法，
    那时才会真正看出它们是同一句。
    """
    ded = []
    for r in out:
        k = norm(r["en"])
        if not k:
            continue
        # 往前看两行：OCR 可能把同一句读成「好的 / 坏的 / 好的」三连，
        # 只比上一行的话中间那张坏牌会把两边隔开、去重失效。
        hit = None
        for p in ded[-2:]:
            kp = norm(p["en"])
            if k == kp or ((k in kp or kp in k) and r["t"] - p["t"] <= 2.5):
                hit = p
                break
        if hit is not None:
            if len(r["en"]) > len(hit["en"]):
                hit["en"] = r["en"]
                hit["cn"] = r["cn"] or hit["cn"]
            continue
        ded.append(dict(r))
    return ded


def tidy(s):
    """OCR 原文字幕是全小写、无标点；把首字母、后句首字母、以及「我」大写。

    故意**不补句末句号**：一条 cue 只是整句的一半，补了会变成
    「a bib. that just is around the neck.」这种断裂的句子；
    句末标点留到整段拼接完再加。
    """
    s = s.strip()
    if not s:
        return s
    # OCR 会把数字和字母黏在一起（the5th / Step1is）；先把序数词保护起来
    s = re.sub(r"(\d+)(st|nd|rd|th)\b", lambda m: m.group(1) + "\x00" + m.group(2), s)
    s = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", s)
    s = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", s)
    s = s.replace("\x00", "")
    s = s[0].upper() + s[1:]
    s = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), s)
    s = re.sub(r"\bi\b", "I", s)                 # i -> I
    s = re.sub(r"\bi'", "I'", s)                 # i'd / i'll / i've / i'm
    # 偶尔 OCR 会把标点连同字一起读出来（good job,Duncan!Great.）——补回空格
    s = re.sub(r"([,;:])(?=[A-Za-z0-9])", r"\1 ", s)
    s = re.sub(r"([.!?])(?=[A-Za-z])", r"\1 ", s)
    s = re.sub(r"\s+([,;:!?])", r"\1", s)        # 去掉标点前多出来的空格
    s = _PUNCT_RUN.sub(_collapse_punct, s)       # 叠在一起的标点只留一个（wet.? -> wet?）
    return _canon(re.sub(r"\s{2,}", " ", s).strip())


# 同一个词的多种拼写（OCR 各家 / 转录各家），统一成课里用的那一种
_CANON = [
    (re.compile(r"\bplay[\s\-]?doh\b", re.I), "playdough"),
    (re.compile(r"\bplay[\s\-]?dough\b", re.I), "playdough"),
]


def _canon(s):
    for rx, w in _CANON:
        s = rx.sub(lambda m: w.capitalize() if m.group(0)[:1].isupper() else w, s)
    return s


def proper_set(words):
    """转录里**每一次出现都大写**的词 = 专有名词（Duncan / Riley / I）。

    whisper 会把每个分段的首字母大写，所以不能直接照抄转录的大小写
    （会在一句话中间冒出 And / So）。只有「从没小写过」的词才值得沿用。
    """
    return proper_and_low(words)[0]


def proper_and_low(words):
    """-> (专有名词, 录音里小写过的词)

    第二个集合给 apply_p2 用来判「句中冒出来的大写是不是断句假象」：
    一个词如果在录音里也小写过（of / and / this / dip），那它句中大写就是
    cue 拼接的副作用；从没小写过的（Duncan / Chinese）才是真专有名词。
    """
    cap, low = set(), set()
    for _t, w in words:
        lw = _nt(w)
        if not lw:
            continue
        (cap if w[:1].isupper() else low).add(lw)
    return cap - low, low


TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9']*")     # 含数字（20 seconds 里的 20）
_NOTOK = re.compile(r"[^a-z0-9']")


def _nt(x):
    """归一化单个词：去标点，保留内撇号（seconds. -> seconds）"""
    return _NOTOK.sub("", x.lower())

# OCR 常把撇号读丢（I d like / don t / it s）——按「左边是哪个词」白名单补回，
# 不做泛化拼接，避免把 banana s 误并成 banana's
_APOS_S = ("it that there what here she he let who where how this when why "
           "baby babies mum mom dad daddy mummy everyone everybody someone somebody "
           "something nothing everything one aunt uncle").split()
_APOS_X = ("i you we they he she it that there who what let").split()
_APOS_R = re.compile(r"\b(%s) (d|m|ll|ve|re)\b" % "|".join(_APOS_X), re.I)


def fix_apos(s):
    s = re.sub(r"\b([A-Za-z]+n) t\b", r"\1't", s)                 # don t -> don't
    s = re.sub(r"\b(%s) s\b" % "|".join(_APOS_S), r"\1's", s, flags=re.I)
    s = _APOS_R.sub(lambda m: "%s'%s" % (m.group(1), m.group(2)), s)
    return s


def asr_words(n):
    """全片转录 → (插值时间, 词, 原文片段) 序列。

    转录只有整段起止时间，没有词级时间戳；段内按词数均分插值，
    精度足够用来「把 OCR 那句在原转录里定位出来」。
    """
    p = os.path.join(ROOT, "work_prep", n, "transcript.json")
    if not os.path.exists(p):
        return []
    try:
        segs = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for sg in segs:
        ws = sg["text"].split()
        if not ws:
            continue
        span = max(sg["end"] - sg["start"], 0.01)
        for j, w in enumerate(ws):
            out.append((sg["start"] + span * j / len(ws), w))
    return out


MIN_SIM = 0.6        # OCR 词 ↔ 转录词 的字符相似度下限（tgothbrush/toothbrush≈0.9）


def _sim(x, y):
    return difflib.SequenceMatcher(None, x, y).ratio()


def _pair(A, Bb, min_sim=MIN_SIM):
    """把两个「替换块」的 a 词与 b 词做 1:1 配对（可跳过任一侧）。

    SequenceMatcher 会把「OCR 尾词 + 后面一整串」并成同一个 replace 块，
    直接按块取 b 会把邻句卷进来；按比例取又会把 `tgothbrush` 整个丢掉。
    这里用带跳过的 DP（Needleman–Wunsch 简化版）在块内做逐词配对，
    得分 = 字符相似度，跳过代价低于任何合格配对。
    """
    n, m = len(A), len(Bb)
    if not n or not m:
        return []
    if n * m > 600:                      # 块太大时退回「等长对位」
        k = min(n, m)
        return [(i, i) for i in range(k) if _sim(A[i], Bb[i]) >= min_sim]
    GAP = -0.35
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
        rowp, rowc, rowb = dp[i - 1], dp[i], bk[i]
        for j in range(1, m + 1):
            s = _sim(ai, Bb[j - 1])
            diag = rowp[j - 1] + (s if s >= min_sim else 2 * GAP)
            up = rowp[j] + GAP
            left = rowc[j - 1] + GAP
            best, k = diag, 0
            if up > best + 1e-9:
                best, k = up, 1
            if left > best + 1e-9:
                best, k = left, 2
            rowc[j] = best
            rowb[j] = k
    pairs, i, j = [], n, m
    while i > 0 and j > 0:
        k = bk[i][j]
        if k == 0:
            if _sim(A[i - 1], Bb[j - 1]) >= min_sim:
                pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif k == 1:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def _known(w, lex):
    """词表里有这个（真）词吗；顺带认 OCR 丢撇号的写法（wheres/cant）"""
    return bool(w) and (len(w) == 1 or enfix._lookup(w, lex)[0] > 0)


def _bare(w):
    """只取词本身，丢掉挂在两端的标点（转录的 Duncan. -> Duncan）

    标点属于相邻的 OCR 文字（它读出来了就留着），不该被替换带进来。
    """
    return re.sub(r"[^A-Za-z0-9']", "", w)


_PUNCT = ".,!?;:"
_PUNCT_RUN = re.compile(r"[,;:.!?]{2,}")


def _collapse_punct(m):
    """连续标点只留一个：wet.? -> wet? / in,, -> in, / shapes.. -> shapes."""
    run = m.group(0)
    for c in ("!", "?"):          # 有问号叹号就留它，句号逗号让位
        if c in run:
            return c
    return run[-1]


def _steal_punct(i, t, w, new, nxt=""):
    """把转录词尾的标点抄给 OCR 词（brushatong 这类刚被换掉的词也适用）。

    烧录字幕大部分无标点，整段拼起来就是「…how to bathe so one huge tip is…」这种
    一口气到底的长句。转录的句子边界未必 100% 对，但比完全没有强得多。
    `nxt` = 这个词后面紧跟的字符：OCR 偶尔也读出了标点（wet? / in,），
    那就不许再叠一个，否则会变成「wet.?」「in,,」。
    """
    if nxt and nxt in _PUNCT:      # 注意 nxt 可能是空串，'' in ".,!?;:" 是 True！
        return
    p = w[-1:] if w else ""
    if p in _PUNCT and t and t[-1] not in _PUNCT:
        new[i] = t + p


def repair(en, lo, hi, words, lex=None, prop=(), min_sim=0.75):
    """OCR 英文行 + 同时间窗的转录文字 -> 只给「读错的词」正名，**不增不删**。

    烧录字幕才是视频里真正出现的字。OCR 会连写、会认错字，但它「有几个词」
    是可信的；转录拼写正确但会听漏、会断句错。所以：
      1. 先 opcode 级比对，块内用 _pair() 做 1:1 配对，得到「词位锚点」；
         相似度够高的错字（tgothbrush→toothbrush、batfery→battery）就地换掉。
      2. 没锚上的 OCR 残片，若正好对上转录的一小串词、且拼起来够像
         （brushatong ↔ brush along），就用那串词替换它 —— 本质是「断开」。
    OCR 里正常、转录里没听到的词一律原样保留，不会因为转录漏听而被删。
    """
    if not words:
        return tidy(en)
    lex = lex if lex is not None else globals()["lex"]()
    B = [w for t, w in words if lo <= t <= hi]
    if len(B) < 2:
        return tidy(en)
    ms = list(TOK.finditer(en))
    if not ms:
        return tidy(en)
    toks = [m.group(0) for m in ms]
    a = [_nt(x) for x in toks]
    b = [_nt(x) for x in B]
    after = [en[m.end():].lstrip()[:1] for m in ms]     # 词后面紧跟的字符

    # --- 1) 词位锚点 ---
    anchor, new = {}, {}
    sm = difflib.SequenceMatcher(None, a, b)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                anchor[i1 + k] = j1 + k
        elif tag == "replace":
            # 先试「一个 OCR 词 = 转录里的一小串词」：OCR 连写/黏连读错，
            # 逐词配对只会挑中最像的那一个、把另一个丢掉
            # （brushatong↔brush along、therchewing↔the chewing）。
            if i2 - i1 == 1 and 1 <= j2 - j1 <= 3 and not _known(a[i1], lex):
                if _sim(a[i1], "".join(b[j1:j2])) >= min_sim:
                    new[i1] = " ".join(_bare(x) for x in B[j1:j2])
                    continue
            for pi, pj in _pair(a[i1:i2], b[j1:j2]):
                anchor[i1 + pi] = j1 + pj

    for i, j in anchor.items():
        t = toks[i]
        if _nt(t) == b[j]:                                   # 同一个词，只补大写
            if _nt(t) in prop and t != _bare(B[j]):
                new[i] = _bare(B[j])                         # 专有名词：Duncan
            # 烧录字幕没有标点，转录有 —— 锚上了就把标点借过来
            _steal_punct(i, t, B[j], new, after[i])
            continue
        if _sim(_nt(t), b[j]) < min_sim:
            continue
        if _known(_nt(t), lex):                              # OCR 本来就是真词 -> 不动
            continue
        if _known(b[j], lex) or B[j][:1].isupper():          # 转录那边得像话
            cand = _bare(B[j])
            if cand:
                new[i] = cand
                _steal_punct(i, cand, B[j], new, after[i])

    # --- 2) 还没被认下来的词 ↔ 转录里的一小串词 ---
    # 「锚上了但相似度不够」的也算没认下来（brushatong 会被锚到 brush 上），
    # 所以这里按「已认下来」的位置划区间，区间内的小残片允许整体换成转录的说法。
    done = sorted(i for i in anchor if _nt(toks[i]) == b[anchor[i]] or i in new)
    free = [i for i in range(len(toks)) if i not in done]
    grp, cur = [], []
    for i in free:
        if cur and i == cur[-1] + 1:
            cur.append(i)
        else:
            if cur:
                grp.append(cur)
            cur = [i]
    if cur:
        grp.append(cur)
    for g in grp:
        if len(g) != 1:
            continue
        i = g[0]
        lo_j = max((anchor[k] for k in done if k < i), default=-1) + 1
        hi_j = min((anchor[k] for k in done if k > i), default=len(b)) - 1
        if not (0 <= lo_j <= hi_j < len(b)) or hi_j - lo_j + 1 > 3:
            continue
        joined = "".join(b[lo_j:hi_j + 1])
        if _sim(_nt(toks[i]), joined) >= min_sim:
            repl = " ".join(_bare(x) for x in B[lo_j:hi_j + 1])
            if repl and repl != toks[i]:
                new[i] = repl

    if not new:
        return tidy(en)
    out, pos = [], 0
    for i, m in enumerate(ms):
        out.append(en[pos:m.start()])
        out.append(new.get(i, m.group(0)))
        pos = m.end()
    out.append(en[pos:])
    return tidy("".join(out))


def fuzzy_dedup(out, thr=0.8, gap=3.0):
    """OCR 错读出来的一对近重复行（battery/batfery、along/brushatong）

    它们在时间上只差 1-2 秒、词集高度重叠，属于「同一 cue 被读了两遍」，
    必须在 repair 之前去掉，否则会以坏拼写进到正文。
    """
    ded = []
    for r in out:
        if ded:
            p = ded[-1]
            if r["t"] - p["t"] <= gap:
                ta = set(_nt(x) for x in TOK.findall(p["en"]))
                tb = set(_nt(x) for x in TOK.findall(r["en"]))
                if min(len(ta), len(tb)) >= 3:
                    j = len(ta & tb) / max(1, len(ta | tb))
                    if j >= thr:
                        if len(r["en"]) > len(p["en"]):
                            p["en"], p["cn"] = r["en"], r["cn"] or p["cn"]
                        continue
        ded.append(r)
    return ded


def build(n, src):
    lines = load_lines(n)
    words = asr_words(n)
    dur = probe_dur(src) if src and os.path.exists(src) else None
    if not lines:
        print("[reseg] %s 没有可用字幕行" % n)
        return None
    lines = fuzzy_dedup(lines)
    prop = proper_set(words)
    for i, r in enumerate(lines):
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else (dur or r["t"] + 2.5)
        r["en"] = fix_apos(repair(r["en"], r["t"] - 2.0, nxt + 1.2, words, prop=prop))
    lines = dedup(lines)
    cuts = []
    for i, r in enumerate(lines):
        a = max(0.0, r["t"] - (PAD_HEAD if i else 0.0))
        b = lines[i + 1]["t"] - PAD_TAIL if i + 1 < len(lines) else (dur or r["t"] + 3.0)
        if b - a < 0.6:                  # 太短的合并给上一段
            if cuts:
                cuts[-1][1] = b
                continue
            b = a + 0.6
        cuts.append([round(a, 2), round(b, 2)])
    segs = []
    for i, (r, c) in enumerate(zip(lines, cuts)):
        # rt = 字幕出现的那一帧（对齐用这个！）；t = 切点起始（= rt - PAD_HEAD）
        segs.append({"no": "%02d" % (i + 1), "en": r["en"], "cn": r["cn"],
                     "t": round(c[0], 2), "rt": r["t"]})
    data = {"n": n, "dur": dur, "cuts": cuts, "segs": segs}
    os.makedirs(os.path.join(ROOT, "work_seg"), exist_ok=True)
    io.open(os.path.join(ROOT, "work_seg", "%s.json" % n), "w", encoding="utf-8").write(
        json.dumps(data, ensure_ascii=False, indent=1))
    print("[reseg] %s dur=%s segs=%d" % (n, dur, len(segs)))
    for s, c in zip(segs, cuts):
        print("  %s  %6.2f-%6.2f  %s\n           中文机翻: %s" % (s["no"], c[0], c[1], s["en"], s["cn"]))
    return data


def main():
    series = json.load(io.open(os.path.join(ROOT, "tools", "series.json"), encoding="utf-8"))
    vdir = series["video_dir"]
    by_n = {l["n"]: l for l in series["lessons"]}
    for n in sys.argv[1:]:
        l = by_n.get(n)
        src = None
        if l:
            v = l["video"]
            src = v if os.path.isabs(v) else os.path.join(vdir, v)
        build(n, src)


if __name__ == "__main__":
    main()
