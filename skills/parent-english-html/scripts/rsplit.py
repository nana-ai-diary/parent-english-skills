# -*- coding: utf-8 -*-
"""给 Part 2 英文补「断句标点」——把一口气到底的长句切成好读的短句。

背景
----
烧录字幕全小写、没标点；ASR 转录（`small + beam_size=1 + temperature=0`）标点又很稀疏。
两边一拼，自然段里就会出现「30~40 个词只有一个句号」的连写长句，家长看着累、
也没法跟中文逐句对照。全系列 Part 2 共 881 句，其中 ≥18 词的有 73 句，最长 41 词。

做法（三步）
------------
1. **候选断点**：跑一遍口语里的「新一句开头」模式 —— 人称代词 + 动词（we can / you want to…）、
   连接副词（and then / now / next…）、let's / make sure / remember…，以及弱转折 so / but / because。
2. **护栏**：候选点会被下面几条否掉
   - 落在已高亮词组内部（`protect`，否则那块 `<span>` 就没了）；
   - 前面是 and / to / that / if …（这种情况下那不是新句子，是从句）；
   - 前三个词里有从句引导词（see **how** long you can ride —— 不能切）。
3. **DP 选点**：在候选点里挑一组，让每句话的长度尽量落在 6~14 词
   （碎片句、巨长句都有代价）。这一步负责收拾「And then for little boys.」这种碎片段。

硬约束
------
- 纯文本操作，**不动 cuts** → 音频视频不用重编码；
- 只在 ≥18 词且没有内部标点的句子上动手，已经在 Granularity 上合适的句子不动。

用法:
  python tools/rsplit.py              # 体检：打印全系列会被改的句子（不写文件）
  python tools/rsplit.py brush 28     # 只看某几课（slug 片段）
"""
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = re.compile(r"<[^>]+>")
SPAN_RE = re.compile(r"<span\s+class=['\"]k\s*([a-z]?)['\"][^>]*>(.*?)</span>", re.S)

WORD = re.compile(r"[a-z0-9']+")
LONG = 18               # 多少词算「长句」

# ---------- 强边界：一句话（一个新主谓结构 / 一个新动作） ----------
# 写法：从断点开始的「词序列」。先列长的（and then），再列短的（then）。
STRONG_HEADS = [
    ("and", "then"), ("and", "now"), ("and", "next"), ("and", "finally"),
    ("and", "first"), ("and", "again"), ("and", "remember"),
    ("and", "make", "sure"), ("and", "that's"), ("all", "right"),
    # 「and / but + 主语」同样是换了一句（and 本身被留到新句子开头）
    ("and", "we"), ("and", "you"), ("and", "i"), ("and", "they"),
    ("and", "he"), ("and", "she"), ("and", "it"), ("and", "this"),
    ("but", "we"), ("but", "you"), ("but", "i"), ("but", "it"),
    ("then",), ("now",), ("next",), ("finally",), ("firstly",), ("first",),
    ("secondly",), ("again",), ("remember",),
    ("we're", "going"), ("we're", "gonna"), ("we", "are"), ("we", "were"),
    ("we", "can"), ("we", "want"), ("we", "need"), ("we", "have"), ("we", "don't"),
    ("we", "didn't"), ("we", "just"), ("we", "make"), ("we", "gotta"), ("we", "got"),
    ("we", "keep"), ("we", "use"), ("we", "do"), ("we", "did"), ("we", "had"),
    ("we", "put"), ("we", "take"), ("we", "add"), ("we", "turn"), ("we", "call"),
    ("we", "would"), ("we", "should"), ("we", "start"), ("we", "get"), ("we", "go"),
    ("we", "wash"), ("we", "pull"), ("we", "fold"), ("we", "repeat"), ("we", "cross"),
    ("we", "bring"), ("we", "hold"), ("we", "open"), ("we", "close"), ("we", "tie"),
    ("we'll",),
    ("you", "want"), ("you", "can"), ("you", "could"), ("you", "should"),
    ("you", "need"), ("you", "have"), ("you", "may"), ("you", "might"),
    ("you", "don't"), ("you", "didn't"), ("you", "gotta"), ("you", "got"),
    ("you", "are"), ("you", "will"), ("you", "keep"), ("you", "put"),
    ("you", "take"), ("you", "add"), ("you", "use"), ("you", "do"),
    ("you", "see"), ("you", "know"), ("you", "cross"), ("you", "make"),
    ("you", "pull"), ("you", "turn"), ("you", "repeat"), ("you", "drag"),
    ("you", "bring"), ("you", "start"), ("you'll",),
    ("i", "want"), ("i", "need"), ("i", "can"), ("i", "just"), ("i", "put"),
    ("i", "take"), ("i", "add"), ("i", "use"), ("i", "think"), ("i", "mean"),
    ("i", "had"), ("i", "have"), ("i", "would"), ("i", "fold"), ("i", "get"),
    ("i'll",), ("i'm", "going"),
    ("they", "can"), ("they", "still"), ("they", "are"), ("they", "were"),
    ("they", "don't"), ("they", "have"), ("they", "wear"),
    ("he", "is"), ("he", "has"), ("he", "can"), ("he", "was"), ("he", "does"),
    ("she", "is"), ("she", "has"), ("she", "can"), ("she", "was"),
    ("that's", "why"), ("that's", "how"), ("that's", "what"), ("that's", "where"),
    ("so", "that's"), ("so", "this"), ("so", "we"), ("so", "you"), ("so", "i"),
    ("so", "they"), ("so", "it's"), ("so", "he"), ("so", "she"), ("so", "first"),
    ("this", "is"), ("this", "way"), ("this", "helps"), ("this", "means"),
    ("it's", "really"), ("it", "is"), ("it", "snaps"), ("it", "should"),
    ("it", "will"), ("it", "doesn't"),
    ("there", "are"), ("there", "shouldn't"), ("there", "is"), ("there", "should"),
    ("let's",), ("let", "me"), ("make", "sure"), ("just", "make"),
    ("another", "thing"), ("the", "next"),
]

# 泛化的「人称代词 + 任意词」——口语里换一句最常见的开口
PRON_HEAD = {"we", "you", "i", "he", "she", "they",
             "we're", "you're", "we'll", "you'll", "he's", "she's", "they're",
             "we've", "you've", "we'd", "you'd", "i'm", "i'll", "let's"}
NOT_VERBISH = {"have", "has", "had", "just", "really", "also", "still", "then",
               "too", "again", "now", "to", "and", "but", "or", "so", "if"}

# 这些词如果前面是限定词 / 量词（the first step），就不是承接副词，不许切
ADV_HEAD = {"then", "now", "next", "finally", "first", "firstly", "secondly",
            "again", "remember"}
DET_PREV = {"the", "a", "an", "of", "at", "in", "on", "to", "for", "with", "from",
            "about", "my", "your", "his", "her", "their", "our", "this", "that",
            "these", "those", "is", "was", "are", "were", "so", "and", "but",
            "then", "up", "out", "into", "onto", "over", "all", "each", "first"}

# ---------- 候选点的额外代价 ----------
# 「and then / now / next」这类承接词单独成句时常常只是半句话
# （*And then for little boys.*），给它一笔「软代价」，让 DP 优先用别的地方落刀。
SOFT_HEADS = {("and", "then"), ("and", "now"), ("and", "next"), ("and", "finally"),
              ("and", "first"), ("and", "again"), ("and", "remember"),
              ("and", "make", "sure"), ("and", "that's"), ("all", "right"),
              ("then",), ("now",), ("next",), ("finally",), ("firstly",),
              ("first",), ("secondly",), ("again",), ("remember",),
              ("first", "we"), ("first", "you"), ("the", "next"), ("next", "we"),
              ("next", "you"), ("another", "thing")}
SOFT_COST = 3.0
# 「so he / so we」这种结果句，句号算合法但不如其它边界干净
SO2_COST = 1.0
SO2_HEADS = {("so", "that's"), ("so", "this"), ("so", "we"), ("so", "you"),
             ("so", "i"), ("so", "they"), ("so", "it's"), ("so", "he"),
             ("so", "she"), ("so", "first")}

# 紧邻前一个词是这些 → 说明后面是从句的一部分，不是新句子
STOP_PREV = {"and", "but", "or", "so", "to", "that", "if", "when", "while",
             "because", "whether", "also", "just", "than", "as", "not",
             "you", "i", "it", "this", "that",
             # what you do **is** you first start… / there **are** so many…
             "is", "are", "was", "were", "be", "been", "being", "am", "'s",
             # 副词性插入语，后面那句还没开始（or **maybe** you make the purees yourself）
             "maybe", "perhaps", "especially", "sure", "such", "except", "plus",
             # wish / hope 后面接的是宾语从句（I sure hope they have something）
             "hope", "think", "guess", "suppose", "believe", "bet", "feel",
             # everything **you** might need —— 后面的从句不能和先行词分开
             "everything", "anything", "something", "nothing", "lots"}
# 承接词（and **then** you…）：不许在它后面落刀（会切成半句），改成落刀在它**前面**
CONNECT = {"then", "now", "okay", "ok", "yes", "alright"}
PRE_CONNECT = {"and", "so", "but", "all", "right"}
# 从句 / 名词短语的开头词：用来判断后面到底有没有一个新句子
CLAUSE_START = {"you", "we", "i", "they", "he", "she", "it", "there", "this",
                "that", "they're", "he's", "she's", "it's", "we're", "you're",
                "the", "your", "my", "his", "her", "their", "our"}
DET_PRE3 = {"your", "my", "the", "a", "an", "his", "her", "their", "our",
            "this", "that", "these", "those"}
# 前三个词里有这些从句引导词 → 同样不许切（see how long you can ride / make sure that…）
SUB_PREV = {"that", "if", "whether", "how", "what", "where", "why", "when", "who",
            "which", "whose", "see", "sees", "let", "lets", "than", "as", "unless",
            "until", "before", "after", "once", "while", "because", "so"}
# 人称代词后面紧跟这些 → 大概率是宾语不是主语（teach **you a** simple recipe）
OBJ_NEXT = {"a", "an", "the", "this", "that", "these", "those", "it", "him", "her",
            "us", "them", "some", "more", "my", "your", "his", "their",
            "it's", "he's", "she's"}
# 落刀点之前（且上一个「句号断点」之后）出现过的从句引导词 → 这一刀只能给逗号
SUBORD_OPEN = {"when", "while", "because", "if", "after", "before", "once",
               "unless", "although", "though", "in"}
SUBORD_PAIR = {("so", "that"), ("in", "order"), ("as", "soon"), ("even", "if")}
# 从句引导词离得太远（>10 词）就认为它已经收尾了，不再把这一刀压成逗号
MAX_OPEN_DIST = 10

# ---------- 弱边界：逗号 ----------
# 句首就是从句引导词时，第一个断点只能给逗号（If X, you will…）
SUB_START = {"if", "when", "while", "because", "although", "as", "since",
             "unless", "after", "before", "once"}
WEAK = {"so", "but", "because", "though", "although", "while", "otherwise"}
WEAK_BLOCK_PREV = {"so", "but", "and", "that", "if", "when", "while", "because",
                   "to", "just", "like", "the", "a", "not",
                   "is", "are", "was", "were", "be", "been", "have", "has", "had"}
# there are **so many** / it's **so that** —— so 修饰的不是整句，别加逗号
WEAK_BLOCK_NEXT = {"many", "much", "few", "little", "that", "this", "cute",
                   "good", "happy", "nice", "easy", "important", "convenient"}

# ---------- 疑问句：首词 + 助动词 → ? ----------
WH = {"how", "what", "where", "why", "when", "who", "which"}
AUX = {"do", "does", "did", "is", "are", "was", "were", "can", "could", "will",
       "would", "should", "shall", "have", "has", "am", "about"}

KEEP = {"i", "i'm", "i'll", "i've", "i'd", "okay", "ok"}

# ---------- DP：句子长度偏好 ----------
def chunk_cost(L):
    """一句话理想长度 6~14 词；碎片和长句都罚分"""
    if L <= 3:
        return 14.0
    if L <= 5:
        return 4.5
    if L <= 14:
        return 0.0
    return 1.4 * (L - 14)


PUNCT_COST = {".": 0.2, "?": 0.2, ",": 1.2}


def words_of(s):
    return s.split()


def _key(w):
    return WORD.sub("", w.lower()) or w.lower()


def protect_spans(text, protect):
    """被保护词组（高亮）在词序列里的区间 -> [(start, end)]（右开）"""
    keys = [_key(t) for t in words_of(text)]
    spans = []
    for p in protect:
        pw = [_key(x) for x in words_of(p)]
        if not pw:
            continue
        for i in range(len(keys) - len(pw) + 1):
            if keys[i:i + len(pw)] == pw:
                spans.append((i, i + len(pw)))
    return spans


def _in_span(pos, spans):
    """在 pos-1 与 pos 之间切断时，是否正好切开了某个被保护词组"""
    return any(s < pos < e for s, e in spans)


def cap(w):
    if not w or _key(w) in KEEP or w[:1].isupper():
        return w
    for i, c in enumerate(w):
        if c.isalpha():
            return w[:i] + c.upper() + w[i + 1:]
    return w


def sentence_mark(first, second):
    if _key(first) in WH and _key(second) in AUX:
        return "?"
    return "."


def _match_head(keys, i, heads):
    for h in heads:
        if tuple(keys[i:i + len(h)]) == h:
            return len(h)
    return 0


def _head_cost(keys, i):
    """该候选点用的是哪个 head -> (长度, 额外代价)"""
    for group, cost in ((SOFT_HEADS, SOFT_COST), (SO2_HEADS, SO2_COST)):
        for h in group:
            if tuple(keys[i:i + len(h)]) == h:
                return len(h), cost
    return _match_head(keys, i, STRONG_HEADS), 0.0


def _open_before(keys, start, i):
    """[start, i) 里有没有「还没收尾」的从句引导词 → 返回它的下标。

    after / before / while 也可能是介词（after every diaper change），
    所以要求它后面紧跟一个从句开头词（you / the / your…）才算从句。
    """
    for j in range(i - 2, max(0, start) - 1, -1):
        if i - j > MAX_OPEN_DIST:
            continue
        w = keys[j]
        if w in SUBORD_OPEN and (w in ("when", "while", "because", "if", "unless")
                                 or keys[j + 1] in CLAUSE_START):
            return j
        if (w, keys[j + 1]) in SUBORD_PAIR:
            return j
    return None


def candidates(keys, spans, n, toks):
    """-> {pos: [(标点, 额外代价)]}，pos 表示在 pos-1 与 pos 之间切断。

    只给自己没标点的地方落刀：前一词已经带逗号时保持原样
    （ASR 给的逗号通常是对的，把它换成句号反而出错）。
    """
    out = {}
    for i in range(1, n):
        if _in_span(i, spans) or re.search(r"[,;:]$", toks[i - 1]):
            continue
        prev = keys[i - 1]
        nxt = keys[i + 1] if i + 1 < n else ""
        L, extra = _head_cost(keys, i)
        generic = keys[i] in PRON_HEAD and i + 1 < n and keys[i + 1] not in NOT_VERBISH
        guard = (keys[i] in ADV_HEAD and prev in DET_PREV) or \
                (prev in STOP_PREV) or \
                (nxt in OBJ_NEXT and generic and not L) or \
                any(keys[j] in SUB_PREV for j in range(max(0, i - 3), i))
        if prev in CONNECT and (L or generic):
            # 「…your first sleeve and then you do the same thing」：
            # 别切成「…and then. You do…」，把这一刀挪到承接词之前
            j = i - 1
            while j - 1 >= 1 and keys[j - 1] in PRE_CONNECT:
                j -= 1
            if j >= 1 and j not in out and not _in_span(j, spans) \
                    and not re.search(r"[,;:]$", toks[j - 1]):
                out[j] = [(".", 0.0)]
        elif (L or generic) and not guard:
            out[i] = [(sentence_mark(keys[i], keys[i + 1] if i + 1 < n else ""), extra)]
    return out


def forced_commas(keys, cands, n):
    """哪些候选点只能给逗号（从句还没收尾 / 句首就是从属连词）。

    逗号不缩短句子，DP 里不参与；这里是「语法修正」，单独加。
    尾巴太短（<6 词）时不给逗号 —— 那种地方断出来通常是新的一句
    （Tell me if X or if Y. **You want** Z.）
    """
    out = []
    if keys and keys[0] in SUB_START:
        for i in sorted(cands):
            if 3 <= i <= n - 5:
                out.append(i)
                break
    mark = out[0] if out else 0
    for i in sorted(cands):
        if i in out or i < mark:
            continue
        j = _open_before(keys, mark, i)
        if j is None:
            continue
        # 重点在这儿：切点前是个名词短语结尾（into **your sleeve** | it doesn't…）
        # 才算「从句刚收尾」，给逗号；切点前是动词（slow **down** | you want…）
        # 说明说话人已经在起新句子了，留句号。
        if keys[i - 2] in DET_PRE3:
            out.append(i)
    for i in out:
        cands.pop(i, None)
    return out


def choose_breaks(n, cands):
    """DP：在候选点里选一组，令 Σ chunk_cost + Σ PUNCT_COST 最小。

    f[i] = 前 i 个词切完的最小代价；转移时 j 是「上一刀的位置」。
    """
    INF = 1e9
    f = [INF] * (n + 1)
    bk = [None] * (n + 1)          # (上一刀位置 j, j 处用的标点)
    f[0] = 0.0
    for i in range(1, n + 1):
        for j in range(0, i):
            if f[j] >= INF:
                continue
            if j == 0:
                c = f[j] + chunk_cost(i)
                if c < f[i]:
                    f[i], bk[i] = c, (0, None)
            else:
                for pn, extra in cands.get(j, []):
                    c = f[j] + PUNCT_COST.get(pn, 0.0) + extra + chunk_cost(i - j)
                    if c < f[i]:
                        f[i], bk[i] = c, (j, (pn, extra))
    if f[n] >= INF:
        return []
    cuts, i = [], n
    while i > 0:
        j, pn = bk[i]
        if j:
            cuts.append((j, pn[0]))
        i = j
    cuts.reverse()
    return cuts, f[n]


def split_sentence(s, protect=()):
    """给一个句子补内部断点；返回新句子（结尾标点保留）"""
    m = re.search(r"([.!?]['\"]?)$", s)
    tail, body = (m.group(1), s[:m.start()]) if m else ("", s)
    toks = words_of(body)
    n = len(toks)
    if n < 8:
        return (body + tail).strip()
    keys = [_key(t) for t in toks]
    spans = protect_spans(body, protect)
    cands = candidates(keys, spans, n, toks)
    fcomma = forced_commas(keys, cands, n)
    for p in fcomma:
        cands.pop(p, None)
    if cands:
        cuts, cost = choose_breaks(n, cands)
    else:
        cuts, cost = [], 1e9
    # 没有句号级的改善就保持原样（只有强制逗号时也算「改了」，因为语法是对的）
    if not cuts and not fcomma:
        return (body + tail).strip()
    if cuts and cost >= chunk_cost(n) - 0.5:
        cuts = []
        if not fcomma:
            return (body + tail).strip()
    todo = [(p, ",") for p in fcomma] + cuts
    todo.sort()
    parts, pos = [], 0
    for p, punct in todo:
        prev = re.sub(r"[.,;:!?]+$", "", toks[p - 1]) + punct
        parts.append(" ".join(toks[pos:p - 1] + [prev]))
        pos = p
    parts.append(" ".join(toks[pos:]))
    out = parts[0]
    for (_p, punct), seg in zip(todo, parts[1:]):
        t2 = seg.split()
        if punct in (".", "?"):
            t2[0] = cap(t2[0])
        out += " " + " ".join(t2)
    return re.sub(r"\s{2,}", " ", (out + tail).strip())


def choose_cost(n, cuts, extras=None):
    total, prev_idx = 0.0, 0
    for k, (p, punct) in enumerate(cuts):
        total += chunk_cost(p - prev_idx) + PUNCT_COST.get(punct, 0.0)
        if extras:
            total += extras[k]
        prev_idx = p
    return total + chunk_cost(n - prev_idx)


def has_inner_punct(s):
    return bool(re.search(r"[,;:]", re.sub(r"[.!?]['\"]?$", "", s)))


# 自动规则不敢动、但又确实是一口气到底的长句（≥20 词且几乎没内部标点）。
# 通用规则在这里要么找不到候选点（前面已经有逗号）、要么切出来是半句，
# 所以人工定断句。**只插标点、只改大小写，绝不增删词** —— 增删词会让
# 英文高亮 span 挂不上（apply_marks 按原文 find）。键是句子原文，重跑幂等。
FIX = {
    "You want to have everything you might need diaper cream, baby wipes a diaper or two "
    "and a change of clothes in case there's a mess.":
        "You want to have everything you might need: diaper cream, baby wipes, a diaper or "
        "two, and a change of clothes, in case there's a mess.",

    "I always put the clean diaper underneath the baby before I start it helps to protect "
    "your bedding and his clothes.":
        "I always put the clean diaper underneath the baby before I start. It helps to "
        "protect your bedding and his clothes.",

    "If they still have an umbilical cord, you will fold it down under the umbilical cord "
    "wash your hands after every diaper change.":
        "If they still have an umbilical cord, you will fold it down under the umbilical "
        "cord. Wash your hands after every diaper change.",

    "Here's how to change a diaper step by step and tips to make it easier for both you "
    "and baby.":
        "Here's how to change a diaper, step by step, and tips to make it easier for both "
        "you and baby.",

    "And we can get those front teeth really well and get the sides of the back on the "
    "chewing surfaces and also on the insides of the teeth.":
        "And we can get those front teeth really well. And get the sides of the back on the "
        "chewing surfaces, and also on the insides of the teeth.",

    "You can kind of hear that floss kind of snapping there between the teeth and that "
    "means we're getting down below where the food likes to get caught.":
        "You can kind of hear that floss kind of snapping there between the teeth. And that "
        "means we're getting down below where the food likes to get caught.",

    "And the next we're gonna use the flosser here to go between Duncan's teeth Duncan's "
    "three and a half.":
        "And the next we're gonna use the flosser here to go between Duncan's teeth. "
        "Duncan's three and a half.",

    "Now all of the items are going down the conveyor belt and the checkout lady is "
    "scanning them.":
        "Now all of the items are going down the conveyor belt, and the checkout lady is "
        "scanning them.",

    "As we go through the bulk section where you can buy items in bulk, you'll see these "
    "bananas in a bag that are on sale.":
        "As we go through the bulk section, where you can buy items in bulk, you'll see "
        "these bananas in a bag that are on sale.",

    "How about we are going to leave it like that and what shape would you like to make?":
        "How about we are going to leave it like that? And what shape would you like to make?",

    "Many people went out frantically searching for him paddling boats on the river and "
    "beating drums in a bid to scare away evil spirits.":
        "Many people went out frantically searching for him, paddling boats on the river "
        "and beating drums in a bid to scare away evil spirits.",

    "They also made sticky rice dumplings to throw in the river so that the fish wouldn't "
    "eat his body and would eat the dumplings instead.":
        "They also made sticky rice dumplings to throw in the river, so that the fish "
        "wouldn't eat his body and would eat the dumplings instead.",

    "And go ahead and try to sit either on a low chair or sit on the ground in front of "
    "your child.":
        "And go ahead and try to sit either on a low chair, or sit on the ground in front "
        "of your child.",

    "So you can put them in a diaper cover and there are so many different types that "
    "people gave me.":
        "So you can put them in a diaper cover, and there are so many different types that "
        "people gave me.",

    "So you could put them in a cute little dress, but you don't want to see their diaper "
    "or maybe you don't want them to get dirty.":
        "So you could put them in a cute little dress, but you don't want to see their "
        "diaper, or maybe you don't want them to get dirty.",

    "We're gonna take off your shirt how are you gonna do it we're gonna get this arm out.":
        "We're gonna take off your shirt. How are you gonna do it? We're gonna get this "
        "arm out.",

    "You got to get it off the heel go go go pull it gently very good that was awesome.":
        "You got to get it off the heel. Go go go, pull it gently. Very good, that was "
        "awesome.",

    "And then thread each leg through all the way to the bottom of the pants so that way "
    "they can see their foot.":
        "And then thread each leg through all the way to the bottom of the pants, so that "
        "way they can see their foot.",

    "So he has all of his back molars so we're going to make sure and I get between those "
    "teeth.":
        "So he has all of his back molars. So we're going to make sure and I get between "
        "those teeth.",

    "A really easy way to check this if you don't have a thermometer, your elbow or your "
    "wrist to check to make sure that it's warm enough for you.":
        "A really easy way to check this, if you don't have a thermometer, your elbow or "
        "your wrist to check, to make sure that it's warm enough for you.",

    "Let's begin by providing a comfortable chair or a comfortable seat for your child to "
    "be, making sure that he's stable and able to put the feet on the ground.":
        "Let's begin by providing a comfortable chair, or a comfortable seat, for your "
        "child to be, making sure that he's stable and able to put the feet on the ground.",

    "It's hard to grab things once you're going.":
        "It's hard to grab things once you're going.",

    "Then, roll them into a corn shape put a red date into the bottom of the corn, and "
    "then add a spoonful of sticky rice.":
        "Then, roll them into a corn shape. Put a red date into the bottom of the corn, and "
        "then add a spoonful of sticky rice.",

    "And at the bottom, it snaps, and this is really convenient because you can just "
    "unsnap it, their belly stays covered and warm, but it's great for the summertime, "
    "which it's not right now.":
        "And at the bottom, it snaps, and this is really convenient because you can just "
        "unsnap it. Their belly stays covered and warm, but it's great for the summertime, "
        "which it's not right now.",
}


def resplit(text, protect=(), long_thr=LONG):
    """整段英文 -> (补充后的英文, [(旧句, 新句)…])

    两趟：先按通用规则把长句切开，**再**逐句对照 FIX 表 —— FIX 的键取自
    「自动切完之后」的句子，所以必须放在第二步；否则原文还没断句时键对不上。
    """
    out, chg = [], []
    for m in re.finditer(r"[^.!?]+[.!?]['\"]?", text):
        s = m.group(0).strip()
        ns = FIX.get(s)
        if ns is None:
            ns = s if len(words_of(s)) < long_thr else split_sentence(s, protect)
        parts = []
        for mm in re.finditer(r"[^.!?]+[.!?]['\"]?", ns):
            q = mm.group(0).strip()
            parts.append(FIX.get(q, q))
        if parts:
            ns = " ".join(parts)
        if ns != s:
            chg.append((s, ns))
        out.append(ns)
    if not chg:
        return text, chg
    return re.sub(r"\s{2,}", " ", " ".join(out)), chg


def marks(en):
    return [m.group(2) for m in SPAN_RE.finditer(en)]


# ---------------- 体检 ----------------
def main():
    picks = [a for a in sys.argv[1:] if not a.startswith("--")]
    total = 0
    remain = []
    for f in sorted(os.listdir(os.path.join(ROOT, "tools", "lessons"))):
        if not f.endswith(".json"):
            continue
        slug = f[:-5]
        if picks and not any(p in slug for p in picks):
            continue
        d = json.load(io.open(os.path.join(ROOT, "tools", "lessons", f), encoding="utf-8"))
        for b in d.get("part2") or []:
            if b.get("type") == "day":
                continue
            en_raw = b.get("en", "")
            en = TAG.sub("", en_raw).strip()
            new, chg = resplit(en, marks(en_raw))
            for s in re.finditer(r"[^.!?]+[.!?]['\"]?", new):
                t = s.group(0).strip()
                if len(t.split()) >= LONG:
                    remain.append((len(t.split()), slug, b["no"], t))
            for old_s, new_s in chg:
                total += 1
                if "--remain" in sys.argv:
                    continue
                print("=" * 78)
                print("[%s/%s]" % (slug, b["no"]))
                print("  旧(%2dw): %s" % (len(old_s.split()), old_s))
                print("  新:       %s" % new_s)
    print("\n共 %d 句会被改" % total)
    remain.sort(reverse=True)
    print("\n仍 ≥%d 词的句子: %d" % (LONG, len(remain)))
    if "--remain" in sys.argv:
        for nw, slug, no, t in remain:
            print("  %2dw [%s/%s] %s" % (nw, slug, no, t))
    else:
        for nw, slug, no, t in remain[:8]:
            print("  %2dw [%s/%s] %s" % (nw, slug, no, t))


if __name__ == "__main__":
    main()
