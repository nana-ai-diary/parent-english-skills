# -*- coding: utf-8 -*-
"""把「按 OCR 校正过的 Part 2」应用到某一课。

用法:
  python tools/apply_p2.py 20 --diff     # 体检：逐段列出 旧英文 / OCR 英文 / 现有中文
  python tools/apply_p2.py 20 --write    # 写回 lessons/<slug>.json
                                          （读 tools/p2/<n>.json 里我手写的 ti/cn/tip/hl）

tools/p2/<n>.json 格式:
  { "01": {"ti":"段标题", "cn":"中文译文", "tip":"可选提示",
           "hl":[["en 里的词", "y|g|b|c", "中文释义"]] }, ... }

cuts / 英文原文 / 高亮迁移 全部自动；我只需要给中文和想加的提示。
"""
import difflib, io, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reseg                                    # noqa: E402  复用 asr_words / proper_set
import rsplit                                   # noqa: E402  长句补断句标点
import cutfit                                   # noqa: E402  切点精修（b 收到末词说完处）

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_RE = re.compile(r"<span\s+class=['\"]k\s*([a-z]?)['\"]"
                    r"(?:\s+title=['\"]([^'\"]*)['\"])?\s*>(.*?)</span>", re.S)
TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"[a-z0-9']+")

PAD_HEAD = 0.30
PAD_TAIL = 0.15

# 个别漏网：OCR 的 cue 边界 / ASR 给错大小写造成的，通用规则判不出来，定向修。
# 键是课号，值是 (原文, 改成)；原文取自 join_run 的原始输出，所以重跑是幂等的。
CAP_FIX = {
    "05": [("teeth duncan's three", "teeth Duncan's three")],
    "13": [("and Dip it", "and dip it"),
           ("look pretty otherwise it won't look that pretty?",
            "look pretty. Otherwise, it won't look that pretty.")],
    "14": [("called Qu Yuan it is said", "called Qu Yuan. It is said")],
    "18": [("Ryan's Elbow pad", "Ryan's elbow pad")],
    # 35 折纸飞机：OCR 把句中的逗号读成句号（视频字幕实为 "But before we start flying,"），
    # 并把 ASR 的段首大写/单字母小写带了进来（"some Forms of small v" → 视频里是
    # "some forms of small V"）。两处都只动大小写与标点，不增删词。
    "35": [("flying. We need to lift up", "flying, we need to lift up"),
           ("some Forms of small v at the back", "some forms of small V at the back")],
}


def plain(s):
    return re.sub(r"\s+", " ", TAG_RE.sub("", s)).strip()


def sim(a, b):
    return difflib.SequenceMatcher(None, plain(a).lower(), plain(b).lower()).ratio()


def toks(s):
    return WORD_RE.findall(plain(s).lower())


def score(seg_text, run_text):
    """段文本 vs 一段 cue 文本的匹配度。

    ASR 出的原稿与烧录字幕常差个别词，所以用「词袋 F1 + 顺序相似度」混合，
    容忍多读/漏读几个词，但乱序或整句不同会显著掉分。
    """
    a, b = toks(seg_text), toks(run_text)
    if not a or not b:
        return 0.0
    ca, cb = Counter(a), Counter(b)
    inter = sum((ca & cb).values())
    cov, prec = inter / len(a), inter / len(b)
    f1 = 2 * cov * prec / (cov + prec) if cov + prec else 0.0
    seq = difflib.SequenceMatcher(None, " ".join(a), " ".join(b)).ratio()
    return 0.55 * f1 + 0.45 * seq


def marks(en):
    return [(m.group(1) or "y", m.group(2) or "", m.group(3)) for m in KEY_RE.finditer(en)]


def apply_marks(en_plain, triples):
    # 按词在英文里出现的先后排序，否则后面的词会盖住前面的、导致丢高亮
    seen = {}
    ordered = []
    for t in triples:
        if t in seen:
            continue
        seen[t] = en_plain.find(t[2])
        ordered.append(t)
    ordered.sort(key=lambda t: (seen[t] if seen[t] >= 0 else 10 ** 6))
    out, cur, lost = "", 0, []
    for color, title, word in ordered:
        i = en_plain.find(word, cur)
        if i < 0:
            lost.append(word)
            continue
        out += en_plain[cur:i]
        attr = (" class='k %s' title='%s'" % (color, title)) if title else (" class='k %s'" % color)
        out += "<span%s>%s</span>" % (attr, word)
        cur = i + len(word)
    out += en_plain[cur:]
    return out, lost


def slug_of(n):
    return [f for f in os.listdir(os.path.join(ROOT, "tools", "lessons"))
            if f.startswith(n + "-")][0][:-5]


# 句中冒出来的大写词（"the shape Of your sand castle"）：前面是词字符就算句中
_MIDCAP = re.compile(r"(?<=[\w']) +([A-Z][A-Za-z']*)")


def _lower_midcase(s, prop, low):
    """把句子中间的孤立大写词降回小写。

    标点补全后，每条 cue 都按「段首大写」处理过，拼起来就会冒出
    「all done And I'm really excited」「the shape Of your…」这种断句假象。

    判定依据是**这个词在转录里小写过没有**（`low` 集合）：
    小写过 = 普通词，句中不必大写（of / and / this / dip）；
    从没小写过 = 专有名词（Duncan / Freddie / Chinese），保持不动。
    真句首（前面是 .!?）由正则本身排除，`I` / `I'xx` 永远不降。
    """
    def f(m):
        w = m.group(1)
        if w == "I" or w[:2] == "I'":
            return " " + w
        lw = w.lower()
        if lw in prop or lw not in low:      # 真专有名词 / 录音里没小写过 -> 不动
            return " " + w
        return " " + lw
    return _MIDCAP.sub(f, s)


def join_run(run, prop=(), low=()):
    """把一段里的若干条 cue 拼成一个自然段。

    烧录字幕没有标点，直接把 cue 用空格接起来会出现
    「a bib. That just is around the neck.」这种中段大写的断裂感；
    所以**上一条没有句末标点**时，把下一条的首字母降下去。
    剩下漏网的（ASR 在本该断句的地方标了标点）交给 _lower_midcase。
    """
    parts = []
    for L in run:
        t = L["en"].strip()
        if not t:
            continue
        if parts and not re.search(r"[.!?]['\"]?$", parts[-1]):
            t = t[0].lower() + t[1:]
        parts.append(t)
    s = " ".join(parts)
    s = re.sub(r"\bi'", "I'", s)                # 续句被降下去的首字母，I 要还回来
    s = re.sub(r"\bi\b", "I", s)
    s = _lower_midcase(s, prop, low)
    if s and not re.search(r"[.!?]['\"]?$", s):
        s += "."
    if s[:1].islower():                          # 段首一律大写
        s = s[0].upper() + s[1:]
    return s


def assign(n, d, lines, line_cuts, dur):
    """把 OCR 字幕行对齐到原稿的每一段（**全局单调 DP**）。

    为什么不用「区间取行」：原稿的 cuts 来自 ASR 段边界，与烧录字幕的 cue 边界
    差半句到一句，按区间取会把「下一段的第一句」抢进本段（整篇系统性错位一格），
    这正是「逐句精听和视频对不上」的根因。

    这里改成：把每段原稿文本当作一个「要匹配的串」，在 OCR cue 序列上做单调、
    不重叠的全局最优切分（DP）。段与段之间自然串起来，不会互抢，也不会漏掉 cue。
    """
    for i, L in enumerate(lines):
        L["end"] = lines[i + 1]["rt"] if i + 1 < len(lines) else (dur or L["rt"] + 2.5)
    oldsegs = [b for b in d["part2"] if b.get("type") != "day"]
    m, nl = len(oldsegs), len(lines)
    NEG = -1e9
    runs = [[] for _ in range(m)]
    if not nl or m > nl:
        # 行不够（理论上不会）-> 退化为按原 cuts 区间取
        cuts = d["cuts"]
        packs = [[] for _ in cuts]
        for L in lines:
            hit = next((i for i, (a, b) in enumerate(cuts) if a <= L["rt"] < b), -1)
            if hit < 0:
                hit = min(range(len(cuts)), key=lambda i: min(abs(L["rt"] - cuts[i][0]),
                                                              abs(L["rt"] - cuts[i][1])))
            packs[hit].append(L)
        runs = packs
    else:
        # dp[k][e] = 前 k 段已排好、且第 k 段的 cue 区间结束于 e 的最高分。
        # 允许段间「跳过」若干条 cue（视频里讲过、但原稿没选的句子），
        # 这样每段的 en 与已有 cn 才是同一句话，不会把邻句硬塞进来。
        # 用 M[k][s] = max_{c<=s} dp[k][c] 把「上一段可以在 s 之前的任意位置收尾」压成 O(1)
        dp = [[NEG] * (nl + 1) for _ in range(m + 1)]
        bk = [[(0, 0)] * (nl + 1) for _ in range(m + 1)]
        for e in range(nl + 1):
            dp[0][e] = 0.0
        for k in range(1, m + 1):
            txt = oldsegs[k - 1].get("en", "")
            M = [NEG] * (nl + 1)
            arg = [0] * (nl + 1)
            best = NEG
            for s in range(nl + 1):
                if dp[k - 1][s] > best:
                    best, arg[s] = dp[k - 1][s], s
                elif s:
                    arg[s] = arg[s - 1]
                M[s] = max(best, NEG)
            for i in range(1, nl + 1):
                for j in range(0, i):
                    if M[j] <= NEG / 2:
                        continue
                    v = M[j] + score(txt, " ".join(L["en"] for L in lines[j:i]))
                    if v > dp[k][i]:
                        dp[k][i], bk[k][i] = v, (j, arg[j])
        end = max(range(nl + 1), key=lambda i: dp[m][i])
        bounds = [(0, 0)] * m
        for k in range(m, 0, -1):
            st, prev_end = bk[k][end]
            runs[k - 1] = lines[st:end]
            bounds[k - 1] = (st, end)
            end = prev_end
        # 段间只漏了 1-2 条 cue：多半是同句被 OCR 漏读，并回前一段，
        # 让 en 与本段已有的 cn 覆盖同一句话；漏得多（换话题的插叙）就留着不认领
        for k in range(m - 1):
            a, b = bounds[k]
            c, e2 = bounds[k + 1]
            gap = c - b
            if runs[k] and runs[k + 1] and 1 <= gap <= 2:
                runs[k] = runs[k] + lines[b:c]
                bounds[k] = (a, c)
        if runs[-1] and bounds[-1][1] < nl - 1 and nl - 1 - bounds[-1][1] <= 2:
            runs[-1] = runs[-1] + lines[bounds[-1][1] + 1:]
    newcuts = []
    for k, (run, seg) in enumerate(zip(runs, oldsegs)):
        if not run:
            newcuts.append(None)
            continue
        a = max(0.0, run[0]["rt"] - PAD_HEAD)      # 提前一点，免得把起音切掉
        b = run[-1]["end"] + PAD_TAIL              # = 下一条字幕出现的时间（本句自然收尾）
        if dur:
            b = min(b, dur)
        if b - a < 0.5:
            b = a + 0.5
        newcuts.append([round(a, 2), round(b, 2)])
    # 没分到行的段：用上一段结尾 / 下一段开头补一个占位切点，保持 cuts 与 segs 1:1
    for k in range(m):
        if newcuts[k] is None:
            prev_b = newcuts[k - 1][1] if k and newcuts[k - 1] else 0.0
            nxt_a = next((c[0] for c in newcuts[k + 1:] if c), dur or prev_b + 3.0)
            newcuts[k] = [round(prev_b, 2), round(max(prev_b + 0.5, nxt_a), 2)]
    # 切点精修：上面的 b 用的是 OCR 整秒帧时间（±1s），会系统性偏晚 →
    # 每段音频末尾多带出后一句的头几个词。用「文本 ↔ 转录词」的全局对齐
    # 把 b 收到「本段最后一个词说完」的位置（不动文本，只动时间）。
    # 精修前的那份（纯 OCR 推算）**原样交出去**，供 cutfit --stat 做前后对比。
    precut = [list(c) for c in newcuts]
    texts = [plain(s.get("en", "")) for s in oldsegs]
    try:
        newcuts, _ci = cutfit.refine(n, texts, newcuts, dur)
    except Exception as e:                              # noqa: BLE001
        print("⚠ cutfit 精修失败，保留原切点: %s" % e)
    return oldsegs, runs, newcuts, [], precut


def main():
    n = sys.argv[1]
    mode = "--write" if "--write" in sys.argv else "--diff"
    slug = slug_of(n)
    lj = os.path.join(ROOT, "tools", "lessons", slug + ".json")
    d = json.load(io.open(lj, encoding="utf-8"))
    sg = json.load(io.open(os.path.join(ROOT, "work_seg", "%s.json" % n), encoding="utf-8"))
    oldsegs, packs, newcuts, orphan, precut = assign(n, d, sg["segs"], sg["cuts"], sg.get("dur"))

    if mode in ("--diff", "--low"):
        thr = 2.0 if mode == "--diff" else 0.80
        for seg, pack, nc in zip(oldsegs, packs, newcuts):
            new_en = " ".join(L["en"] for L in pack) or "(无字幕行)"
            r = sim(seg.get("en", ""), new_en) if pack else 0
            if r >= thr:
                print("%s  sim=%.2f  OK" % (seg["no"], r))
                continue
            print("=" * 78)
            print("%s  %.2f-%.2f  相似度 %.2f" % (seg["no"], nc[0], nc[1], r))
            print("  旧: %s" % plain(seg.get("en", "")))
            print("  新: %s" % new_en)
            print("  中: %s" % seg.get("cn", ""))
            if pack:
                lost = [w for _c, _t, w in marks(seg.get("en", "")) if w.lower() not in new_en.lower()]
                if lost:
                    print("  ⚠ 高亮词在新英文里找不到: %s" % " / ".join(lost))
        if orphan:
            print("=" * 78)
            print("未认领的行:")
            for L in orphan:
                print("   %s %6.2f %s | %s" % (L["no"], L["t"], L["en"][:70], L["cn"][:30]))
        return

    # ---- 写回 ----
    p2path = os.path.join(ROOT, "tools", "p2", "%s.json" % n)
    doc = json.load(io.open(p2path, encoding="utf-8")) if os.path.exists(p2path) else {}
    if doc.get("manual"):
        print("[apply] %s 标记 manual，part2 由人工维护，跳过写回" % n)
        return
    hand = doc.get("segs", {})
    prop, low = reseg.proper_and_low(reseg.asr_words(n))   # 专有名词 / 小写过的词
    segs = []
    for i, (seg, pack, nc) in enumerate(zip(oldsegs, packs, newcuts), 1):
        no = "%02d" % i
        en_plain = join_run(pack, prop, low)
        for _a, _b in CAP_FIX.get(n, []):
            en_plain = en_plain.replace(_a, _b)
        triples = marks(seg.get("en", ""))
        h = hand.get(no) or hand.get(seg["no"]) or {}
        if h.get("en"):                     # 手写覆盖：OCR 读不到的段落（字母歌等）
            en_plain = h["en"]
        else:
            # 长句拆分：只动文本，不动 cuts（保护区间避开已高亮的词组）
            en_plain, chg = rsplit.resplit(en_plain, protect=[t[2] for t in triples])
            for old_s, new_s in chg:
                print("   ✂ %s | %s\n     -> %s" % (seg["no"], old_s, new_s))
        if not en_plain:
            en_plain = plain(seg.get("en", ""))
        for item in h.get("hl", []):
            triples.append(tuple(item))
        en_html, lost = apply_marks(en_plain, triples)
        item = {"type": "seg", "no": no, "audio": "seg%s.mp3" % no, "slow": "seg%s_slow.mp3" % no,
                "ti": h.get("ti", seg.get("ti", "")), "en": en_html,
                "cn": h.get("cn", seg.get("cn", ""))}
        tip = h.get("tip", seg.get("tip"))
        if tip:
            item["tip"] = tip
        if seg.get("gram"):
            item["gram"] = seg["gram"]
        segs.append(item)

    # Part 6 第一栏：必须是「中式英语的英文说法」，不能是中文
    p6 = doc.get("part6")
    if p6 and "rows" in p6:
        d["part6"]["rows"] = p6["rows"]
    if p6 and "lead" in p6:
        d["part6"]["lead"] = p6["lead"]
    if p6 and "card" in p6:
        d["part6"]["card"] = p6["card"]
    # 只换第一栏（第二、三栏原样保留，避免重抄出错）
    pc1 = doc.get("part6_col1")
    if pc1 is not None:
        rows = d["part6"]["rows"]
        if len(pc1) != len(rows):
            print("⚠ part6_col1 行数 %d != 原表 %d" % (len(pc1), len(rows)))
        for r, c1 in zip(rows, pc1):
            r[0] = c1

    # Part 7：纯动作教学课没有真正的文化内容 -> 整节去掉
    if doc.get("drop_part7"):
        d.pop("part7", None)

    old_days = [b for b in d["part2"] if b.get("type") == "day"]
    titles = [b.get("t", "Day %d" % (i + 1)) for i, b in enumerate(old_days)]
    while len(titles) < 3:
        titles.append("Day %d" % (len(titles) + 1))
    per = (len(segs) + 2) // 3
    newp2 = []
    for di in range(3):
        chunk = segs[di * per:(di + 1) * per]
        if not chunk:
            continue
        newp2.append({"type": "day", "id": "d%d" % (di + 1), "t": titles[di]})
        newp2.extend(chunk)
    d["part2"] = newp2
    d["cuts"] = newcuts
    io.open(os.path.join(ROOT, "work_seg", "%s.precut.json" % n), "w", encoding="utf-8").write(
        json.dumps({"cuts": precut}, ensure_ascii=False))
    io.open(lj, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    miss = [s["no"] for s in segs if not s["cn"]]
    print("[apply] %s 段=%d cuts=%d part7=%s 缺中文=%s"
          % (n, len(segs), len(newcuts), "有" if d.get("part7") else "已删", miss or "无"))
    print("written", lj)


if __name__ == "__main__":
    main()
