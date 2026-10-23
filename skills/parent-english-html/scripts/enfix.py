# -*- coding: utf-8 -*-
"""修 OCR 出来的连写英文。

烧录字幕字距紧时，OCR 会把一句话读成一个长 token：
    Washyourhands / ourfirststopisthefreefruitsnackforkids / somelemons
给学习页看太丑，所以按「词典 + 词频」做动态规划断词。

词典来源（自带，不依赖第三方包）：
  1. 全系列原稿 part2 的英文（人工/ASR 写的干净英语）
  2. OCR 语料里本身就正常的分词
  3. 一小撮功能词兜底
"""
import io, json, math, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MIN_LEN = 5           # 未收录 token 短于此长度一律不动（避免误拆）
MAX_PIECE = 16
# 通用英文词表（google-10000-english，见 tools/data/en10k.txt），只做兜底
WORDLIST = os.path.join(ROOT, "tools", "data", "en10k.txt")
# 允许独立成词的二字母（其余二字母碎片一律视为噪声）
ALLOW2 = {"am", "an", "as", "at", "be", "by", "do", "go", "he", "if", "in",
          "is", "it", "me", "my", "no", "of", "on", "or", "so", "to", "up", "us", "we"}
FREQ_CAP = 4.0        # 频次的 log 封顶
PIECE_COST = 6.0      # 每片固定代价 -> 片数少的切分才划算
FALLBACK = """a an the and or but if so then than that this these those there here
i you he she it we they me him her us them my your his its our their
is am are was were be been being do does did done doing have has had having
not no yes to of in on at by for with from into onto over under out up down
can could will would shall should may might must let lets
what when where who whom which why how all any some every each both few more most
one two three four five six seven eight nine ten
go goes going went gone get gets got make makes made put puts take takes took
wash hands hand tooth teeth brush brushes mouth face water soap wet dry
first next last again start stop wait look see watch ready right left
baby babies child children kid kids mum mom dad daddy mummy
please thank thanks sorry okay ok yeah yep nope
on sale for sale more most
im i'm i'll i've ill youre you're were we're they're dont don't doesnt doesn't
didnt didn't cant can't wont won't isnt isn't arent aren't wasnt wasn't
couldnt couldn't shouldnt shouldn't its it's thats that's theres there's lets let's
"""
# 补充：这些词只在个别视频里出现，转录稿覆盖不到，漏了会被 DP 拆错
# （如 ahead -> a head / together -> to get her / along -> a long）
EXTRA = """
together ahead along around inside insides outside behind beside between
appreciate communities remember understand beautiful wonderful important
"""


def _words(text):
    return re.findall(r"[A-Za-z][A-Za-z']*", text)


_TOTAL = [0.0]      # 词表总频次（unigram 语言模型的归一化分母）


def build_lexicon(extra=(), lessons=True):
    """词表 = 原稿英文 + 全片 ASR 转录 + 兜底功能词。

    注意：**不要**吸收 OCR 语料——连写词（whereI / somelemons）一旦进表，
    就会被当成合法单词，再也不会被拆开。
    `lessons=False` 时连 tools/lessons/*.json 也不收：那些 part2 的 en 是
    apply_p2 从 OCR 回写的，里面带着 OCR 的错字（tgothbrush / agalin），
    收进来会让「错字」变成合法词、再也纠不回来（自污染闭环）。
    """
    cnt = {}

    def feed(text, w):
        for x in _words(re.sub(r"<[^>]+>", " ", text)):
            xl = x.lower()
            if len(x) == 1 and xl not in ("a", "i"):
                continue
            if len(x) == 2 and xl not in ALLOW2:
                continue
            cnt[xl] = cnt.get(xl, 0) + w

    if lessons:
        ldir = os.path.join(ROOT, "tools", "lessons")
        for f in os.listdir(ldir):
            if not f.endswith(".json"):
                continue
            try:
                d = json.load(io.open(os.path.join(ldir, f), encoding="utf-8"))
            except Exception:
                continue
            for b in d.get("part2", []):
                if b.get("type") != "day":
                    feed(b.get("en", ""), 3)
    # 全片转录（faster-whisper small）：分词干净，是最好的补词来源
    pdir = os.path.join(ROOT, "work_prep")
    if os.path.isdir(pdir):
        for sub in os.listdir(pdir):
            tp = os.path.join(pdir, sub, "transcript.txt")
            if os.path.exists(tp):
                feed(io.open(tp, encoding="utf-8", errors="ignore").read(), 2)
    feed(FALLBACK, 5)
    feed(EXTRA, 5)
    # 通用词表最后加，权重最低：只是让 youto / knowthe / somelemons 能拆开，
    # 不能盖过领域词（teeth / scooter / playdough 等来自转录稿的拼写）。
    # 注意：google-10000-english 里混着 nd / tf / ou / ge 这种二字母垃圾，
    # 必须滤掉——否则 DP 会拿碎片凑分，把 sitting 拆成 si tt ing。
    if os.path.exists(WORDLIST):
        for ln in io.open(WORDLIST, encoding="utf-8", errors="ignore"):
            w = ln.strip().lower()
            if not w.isalpha():
                continue
            if len(w) == 2 and w not in ALLOW2:
                continue
            if len(w) > 1:
                cnt.setdefault(w, 1)
    for w in extra:
        cnt[w.lower()] = cnt.get(w.lower(), 0) + 5
    _TOTAL[0] = float(sum(cnt.values()))
    return cnt


def _suspicious(w, lex):
    if w.lower() in lex:
        return False
    core = w.replace("'", "")
    if len(core) < MIN_LEN:
        # 中段有大写（whereI / someLemons）也算可疑
        if re.search(r"[a-z][A-Z]", core[1:] or ""):
            return True
        return False
    return True


def _lookup(p, lex):
    """查词；顺带兜住 OCR 丢掉的撇号（wheres -> where's / cant -> can't）"""
    f = lex.get(p, 0)
    if f:
        return f, p
    if len(p) >= 3 and p not in ("and", "the"):
        for i in range(1, len(p)):
            q = p[:i] + "'" + p[i:]
            g = lex.get(q, 0)
            if g:
                return g, q
    return 0, p


def split_token(w, lex):
    """把连写 token 拆回词组；拆不动就原样返回

    评分用标准 unigram 语言模型：score = Σ log2(freq_i / TOTAL) - 0.5。
    关键点是每片都要付「概率代价」（负值），所以碎片越多总分越低——
    否则 app + rec + I + ate 会赢过 appreciate。
    只有「每一片都是词典里真实存在的词」时才考虑拆分。
    """
    if not _suspicious(w, lex):
        return w
    lw = w.lower()
    n = len(lw)
    best = [-1e9] * (n + 1)
    bk = [0] * (n + 1)
    bq = [""] * (n + 1)
    best[0] = 0.0
    for i in range(1, n + 1):
        for j in range(max(0, i - MAX_PIECE), i):
            if best[j] <= -1e8:
                continue
            p = lw[j:i]
            if not re.match(r"^[a-z']+$", p):
                continue
            f, q = _lookup(p, lex)
            if not f:
                continue                        # 碎片一律不要
            # 频次封顶，否则 I / the 这类高频词会把词条硬拆成单字凑分
            v = best[j] + min(math.log(f + 1, 2), FREQ_CAP) - PIECE_COST
            if v > best[i]:
                best[i], bk[i], bq[i] = v, j, q
    if best[n] <= -1e8:
        return w
    pieces, i = [], n
    while i > 0:
        j = bk[i]
        pieces.append(bq[i])
        i = j
    pieces.reverse()
    if len(pieces) < 2 or not all(_lookup(p, lex)[0] for p in pieces):
        return w
    out = []
    for k, p in enumerate(pieces):
        if k == 0 and w[:1].isupper():
            p = p[0].upper() + p[1:]
        out.append(p)
    s = " ".join(out)
    s = re.sub(r"\bi\b", "I", s)                # 单独的 i 还原成 I
    s = re.sub(r"\bi'", "I'", s)
    return s


def fix_line(text, lex):
    """对整行英文做一次断词修复（保序、保标点）"""
    out = []
    for m in re.finditer(r"[A-Za-z][A-Za-z']*|[^A-Za-z]+", text):
        tok = m.group(0)
        out.append(split_token(tok, lex) if tok[:1].isalpha() else tok)
    return "".join(out)
