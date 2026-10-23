# -*- coding: utf-8 -*-
"""亲子英语系列 · 单课 HTML 生成器
用法: python build_lesson.py lessons/02-diaper-change.json
读取 tools/shell.html 作为外壳，用 lesson.json 渲染正文，输出到
outputs/亲子英语/<slug>/index.html
"""
import io, json, os, re, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
SHELL = io.open(os.path.join(BASE, "shell.html"), encoding="utf-8").read()

PARTS = [
    ("how", "怎么用"),
    ("part1", "Part 1｜听原声"),
    ("part2", "Part 2｜逐句精听"),
    ("part3", "Part 3｜学词汇"),
    ("part4", "Part 4｜学句子"),
    ("part5", "Part 5｜练一练"),
    ("part6", "Part 6｜避开中式英语"),
    ("part7", "Part 7｜文化贴士"),
    ("me", "关注我"),
]

# 逐句精听里英文高亮 span -> 取出 (词, 中文释义)；用于把对应中文加粗
CJK = re.compile(r"[\u4e00-\u9fff]")

KEY_RE = re.compile(
    r"<span\s+class=['\"]k\s*([a-z]?)['\"]"
    r"(?:\s+title=['\"]([^'\"]*)['\"])?\s*>(.*?)</span>", re.S)

UNMATCHED = []      # (slug, 段号, 释义) —— 中文里没找到对应词时记录

SLUG = ""           # 当前课 slug（build() 里设置，供 render_seg 记录未匹配项）


def keys_of(en_html):
    """按出现顺序取出 (词, 颜色, title)"""
    return [(m.group(3), m.group(1) or "y", m.group(2) or "")
            for m in KEY_RE.finditer(en_html)]


def plain(s):
    """去掉标签，留纯文本"""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


_ANNOT = re.compile(r"[（(][^（()）]*[)）]")          # 「关掉（电器）」这类注释
_SPLIT = re.compile(r"[／/、，,；;：:—–]+")


def _lcs(a, b):
    """最长公共子串——释义与译文说法不同时的最后兜底（婴儿摇篮 ↔ 小摇篮）"""
    if not a or not b:
        return ""
    prev = [0] * (len(b) + 1)
    best, bi = 0, 0
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        ai = a[i - 1]
        for j in range(1, len(b) + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, bi = cur[j], i
        prev = cur
    return a[bi - best:bi]


def _cn_hit(cn, zh, cur):
    """在中文译文里定位这条释义，由严到宽四级；返回 (下标, 命中的那段文字)。

    1) 原样找
    2) 去掉括号注释再找（关掉（电器）→ 关掉）
    3) 按「、／，」拆成并列说法逐个试（能翻动、会挪动）
    4) 取释义与译文的最长公共子串（使窒息 ↔ 造成窒息 → 窒息）
    都对不上就返回 (None, None)，不硬塞，避免标错地方。
    """
    head = cn[cur:]
    i = head.find(zh)
    if i >= 0:
        return cur + i, zh
    bare = _ANNOT.sub("", zh).strip()
    if bare and bare != zh:
        i = head.find(bare)
        if i >= 0:
            return cur + i, bare
    for piece in sorted(_SPLIT.split(bare or zh), key=len, reverse=True):
        if len(piece) >= 2:
            i = head.find(piece)
            if i >= 0:
                return cur + i, piece
    hit = _lcs(bare or zh, head)
    if len(hit) >= 2:
        return cur + head.find(hit), hit
    return None, None


def hl_cn(cn, en_html, slug="", no=""):
    """把英文高亮的词，在中文里用**同色**标出来 —— 一眼看出哪句英文对应哪句中文。

    只有 title 是中文释义时才标；全称/语法说明（英文）跳过。
    两趟走：先按顺序配对（英文语序 ≈ 中文语序），没配上的再回全句里找
    ——中英语序经常不同（turn off the sound machine → 把白噪音机关掉），
    只按顺序搜会把后一个词漏掉。标错位置的宁可不标，记进 UNMATCHED。
    """
    if not cn or "<span" in cn:
        return cn
    marks = [(c, z.strip()) for _w, c, z in keys_of(en_html)
             if z and z.strip() and CJK.search(z.strip())]
    taken, out, pend = [], [], []

    def free(i, j):
        return all(j <= a or i >= b for a, b in taken)

    def claim(i, hit, color):
        taken.append((i, i + len(hit)))
        out.append((i, i + len(hit), color, hit))

    cur = 0
    for color, zh in marks:                       # ① 顺序配对
        i, hit = _cn_hit(cn, zh, cur)
        if i is not None and free(i, i + len(hit)):
            claim(i, hit, color)
            cur = i + len(hit)
        else:
            pend.append((color, zh))
    for color, zh in pend:                        # ② 回头在全句里找
        pos, done = 0, False
        for _ in range(4):
            i, hit = _cn_hit(cn, zh, pos)
            if i is None:
                break
            if free(i, i + len(hit)):
                claim(i, hit, color)
                done = True
                break
            pos = i + 1
        if not done:
            UNMATCHED.append((slug, no, zh))
    out.sort()
    parts, cur = [], 0
    for i, j, color, hit in out:
        if i < cur:
            continue
        parts.append(cn[cur:i])
        parts.append("<span class=\"k %s\">%s</span>" % (color, hit))
        cur = j
    parts.append(cn[cur:])
    return "".join(parts)


def esc(s):
    return s


def render_toc(skip=()):
    out = ['<nav class="toc">', '  <div class="t">目录</div>']
    for aid, label in PARTS:
        if aid in skip:
            continue
        out.append('  <a href="#%s">%s</a>' % (aid, label))
    out.append("</nav>")
    return "\n".join(out)


def render_hero(d):
    tags = "".join(
        '<span class="tag %s"%s>%s</span>' % (
            t.get("c", ""), (' title="%s"' % t["title"]) if t.get("title") else "", t["t"])
        for t in d.get("tags", []))
    return f'''<div class="hero">
  <h1>{d["zh"]}<span class="en">{d["en"]}</span></h1>
  <div class="srcbar">
    <span class="s">{d.get("source","")}</span>
    <span class="tags">{tags}</span>
  </div>
</div>'''


def render_how(d):
    return '''<section id="how">
  <div class="base-card">
    <div class="bt">怎么用 · 先认领自己的路线</div>
    <p class="lead">点一下你属于哪一类，展开你的走法（会记住你的选择）。</p>

    <div class="picker" id="picker">
      <button class="pcard" data-route="lazy" type="button">
        <span class="pe2">⚡</span><span class="pt">懒人路线</span>
        <span class="pd">每天 2 分钟 · 不用碰原版视频</span>
      </button>
      <button class="pcard" data-route="normal" type="button">
        <span class="pe2">📖</span><span class="pt">系统学习</span>
        <span class="pd">每天 5 分钟 · 从盲听到会说</span>
      </button>
    </div>

    <div class="rbody">
      <div class="rhint" id="rhint">👆 点上面任意一张卡片，展开你的专属走法</div>

      <div class="rpanel" data-route="lazy">
        <ol class="steps">
          <li class="step"><i>1</i><div class="sd">打开 <a class="jump" href="#part4">Part 4 场景常用句</a>，挑 2 句</div></li>
          <li class="step"><i>2</i><div class="sd">当天对宝宝说</div></li>
          <li class="step"><i>3</i><div class="sd">回来打勾</div></li>
        </ol>
        <div class="rn">直接学、直接背就行；有余力再回头啃原版视频。</div>
      </div>

      <div class="rpanel" data-route="normal">
        <ol class="steps">
          <li class="step"><i>1</i><div class="sd"><a class="jump" href="#part1">Part 1</a> 先盲听音频，再看视频做可理解输入</div></li>
          <li class="step"><i>2</i><div class="sd"><a class="jump" href="#part2">Part 2</a> 精听：中英对照，不会的重点听 → 跟读 + 挖空</div></li>
          <li class="step"><i>3</i><div class="sd">熟练后：遮中文说英文、遮英文练翻译</div></li>
          <li class="step"><i>4</i><div class="sd">后续 Part 照此推进，不会的点 ⭐ 收藏</div></li>
        </ol>
        <div class="rn">按 Part 顺序往下走，每天 5 分钟，一步一步来。</div>
      </div>
    </div>

    <p class="shared">📅 <b>[3天场景开口法]</b>：每天2句 · 3天一个场景，<b><a class="jump" href="#part2">Part 2</a> 已按 Day 1 / 2 / 3 分好段</b>，每天 5 分钟；复习时对照 <b><a class="jump" href="#part3">Part 3 词汇表</a></b>、<b><a class="jump" href="#part4">Part 4 场景常用句</a></b>、<b><a class="jump" href="#part5">Part 5 练习</a></b> 查熟练度。</p>

    <div class="tiny">
      <p>🖱 鼠标悬停高亮词可看中文释义</p>
      <p>👆 点击右上角，可遮挡中文、英文和高亮的重点部分</p>
      <p>🔊 点喇叭可听发音（优先 Ana 音色，需 Chrome / Edge / Safari）</p>
      <p>⭐ 点击星星可加入复习清单，但目前复习清单仅保留在您的设备中，无法跨设备使用</p>
    </div>
  </div>
</section>'''


def render_part1(p):
    return f'''<section id="part1">
  <h2><span class="num">Part 1</span>听原声<span class="opt">先盲听 · 再看视频</span></h2>
  <p style="color:var(--muted);font-size:14.5px">{p["blurb"]}</p>

  <div class="card">
    <div class="playrow">
      <audio controls preload="none" id="fullAudio" src="{p["full"]}"></audio>
      <div class="rates" data-for="fullAudio">
        <span class="lb">速度</span>
        <button class="rbtn" data-rate="1.25">1.25×</button>
        <button class="rbtn on" data-rate="1">1×</button>
        <button class="rbtn" data-rate="0.8">0.8×</button>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <div style="font-weight:700;margin-bottom:8px">{p.get("video_title","原版视频")}</div>
    <div class="vwrap">
      <video id="mainVideo" controls preload="metadata" playsinline poster="{p["poster"]}">
        <source src="{p["video"]}" type="video/mp4">
      </video>
      <div class="vrates" data-for="mainVideo">
        <span class="lb">速度</span>
        <button class="rbtn" data-rate="1.25">1.25×</button>
        <button class="rbtn on" data-rate="1">1×</button>
        <button class="rbtn" data-rate="0.8">0.8×</button>
      </div>
    </div>
  </div>
</section>'''


def render_seg(s):
    extra = ""
    if s.get("gram"):
        extra += '\n      <div class="gram"><b>📌 长难句</b> %s</div>' % s["gram"]
    if s.get("tip"):
        extra += ('\n      <div class="note">\n        <span class="t" style="font-weight:700;display:block;margin-bottom:2px;color:var(--accent-ink)">💡 关键信息</span>\n        %s\n      </div>' % s["tip"])
    if s.get("note"):
        extra += ('\n      <div class="note">\n        <span class="t" style="font-weight:700;display:block;margin-bottom:2px;color:var(--accent-ink)">%s</span>\n        %s\n      </div>' % (s["note"]["t"], s["note"]["body"]))
    if s.get("warn"):
        extra += ('\n      <div class="note warn" style="margin-bottom:0">\n        <span class="t">%s</span>\n        %s\n      </div>' % (s["warn"]["t"], s["warn"]["body"]))
    cn = hl_cn(s.get("cn", ""), s.get("en", ""), SLUG, s.get("no", ""))
    return f'''  <div class="seg">
    <div class="seg-h"><span class="no">{s["no"]}</span><span class="ti">{s["ti"]}</span></div>
    <div class="seg-b">
      <div class="pe">
        <audio controls preload="none" src="audio/{s["audio"]}" data-slow="audio/{s["slow"]}" data-normal="audio/{s["audio"]}"></audio>
        <button class="pbtn" data-act="slow">🐢 慢速</button>
        <button class="pbtn" data-act="loop">🔁 循环</button>
      </div>
      <div class="en" style="margin-top:10px">{s["en"]}</div>
      <div class="cn">{cn}</div>{extra}
    </div>
  </div>'''


SENT = re.compile(r"(?<=[.!?])\s+")
# 「关键动作」句：祈使 / 提议 / 提醒，都是能直接对孩子说出口的
_ACT = re.compile(r"^(?:let'?s|let us|please|don'?t|do not|remember to|make sure|be careful|"
                  r"watch out|look out|never|always|wait|stop|hold|get|put|take|give|come|go|"
                  r"try|keep|turn|open|close|wash|dry|wipe|brush|rinse|zip|button|tie|pull|"
                  r"push|sit|stand|look|listen|count|pick|check|start|help|show|use|bring|"
                  r"can you|could you|will you|would you|want to|need to|have to)\b", re.I)
# 这些开头的多半是上一句的尾巴，不是一句完整的话
_FRAG = re.compile(r"^(?:and|so|but|because|then|or|if|when|while|that|which|there)\b", re.I)
GOAL_N = 2                       # 每天只记 2 句：含关键动作、能直接开口说
# 有些段整段就是一句（烧录字幕没标点），一口气念不完；
# 截到第一个从句连接词为止，留「关键动作」那一半
# 注意：**不要**收 if / before / after —— 它们常出现在半句中间，
# 一刀切下去会留下「Always start with clean hands and.」这种断尾
_TRIM = re.compile(r"\s+(?:so that|when|because|while|since|until|unless|and then|"
                   r"in order to|to make sure|which)\b", re.I)
_TAILP = re.compile(r"[,;:]$")
_DANGLE = re.compile(r"\s+(?:and|so|but|or|then|that|the|a|an|to|of|with|for|is|are)\s*$", re.I)


def _shorten(s):
    if len(s.split()) <= 14:
        return s
    m = _TRIM.search(s)
    if not m:
        return s
    head = _DANGLE.sub("", _TAILP.sub("", s[:m.start()]).strip())
    if len(head.split()) < 4:
        return s
    return head + "."


# 整段连读、连逗号都没有时的最后兜底：按这些词把长句切成子句
_CLAUSE = re.compile(r",\s+|\s+(?:and then|and|so|but|then|because)\s+", re.I)


def _clauses(s):
    """把没有句末标点的超长句切成若干子句（>=5 词才留），取不出来就原样返回。

    切出来的片段**补上首字母大写和句末句号**：它们是完整子句
    （"one side has holes in them," 断在逗号上），补完就是能直接背的一句，
    否则会露出「one side has holes in them」这种没头没尾的样子。
    """
    parts, last = [], 0
    for m in _CLAUSE.finditer(s):
        if len(s[last:m.start()].split()) >= 5:      # 太短的碎片不值得单独成句
            parts.append(s[last:m.start()].strip())
            last = m.end()
    tail = s[last:].strip()
    if tail:
        parts.append(tail)
    parts = [p for p in parts if len(p.split()) >= 5]
    if not parts:
        return [s]
    out = []
    for p in parts:
        p = p.strip().rstrip(",;:")
        if not p:
            continue
        p = p[0].upper() + p[1:]
        if p[-1] not in ".!?":
            p += "."
        out.append(p)
    return out or [s]


def _goal_score(s, keys):
    s = _shorten(s)
    n = len(s.split())
    if n < 3:
        return -99.0
    sc = -max(0, n - 8) * 1.0                 # 越长越不值得背
    if n <= 12:
        sc += 2.0
    if _ACT.match(s):
        sc += 3.5
    if _FRAG.match(s):
        sc -= 3.5
    if s.rstrip()[-1:] not in ".!?":
        sc -= 2.0
    if _DANGLE.search(s.rstrip()[:-1] if s.rstrip()[-1:] in ".!?" else s):
        sc -= 4.0                             # 断在连词/介词上的不要
    hit = sum(1 for k in keys if k and k.lower() in s.lower())
    sc += min(hit, 2) * 1.2                   # 含本课重点词的优先
    return sc


def day_goals(blocks, hand=None):
    """每个 Day 挑 2 句**含关键动作**的短句当「今日要掌握」。

    整段英文是连着讲的一大段（十几秒一口气），照搬进来就是一堵墙；
    这里按句切开打分：祈使/提议 +3、含本课重点词 +1.5/个、太长的扣分、
    以 and/so 开头的片段扣分。取分数最高的 2 句，按原文顺序排回。
    """
    buckets, cur = {}, None
    for b in blocks:
        if b["type"] == "day":
            cur = b["id"]
            buckets[cur] = []
        elif cur:
            buckets[cur].append(b)
    out = {}
    for did, segs in buckets.items():
        if hand and hand.get(did):
            out[did] = list(hand[did])
            continue
        cand, i = [], 0
        for b in segs:
            keys = [w for w, _c, _t in keys_of(b.get("en", ""))]
            txt = plain(b.get("en", ""))
            for s in SENT.split(txt):
                s = s.strip()
                if len(s.split()) < 3:
                    continue
                # 整段连读（没句号也没逗号可切）时会很长，先按子句拆开再挑，
                # 每个子句都当候选；实在拆不开的（02/03 那种）才原样留着，
                # 那几课由 tools/goals.json 手写覆盖
                pieces = _clauses(s) if len(s.split()) > 14 else [s]
                for p in pieces:
                    p = p.strip()
                    if len(p.split()) < 3:
                        continue
                    cand.append((_goal_score(p, keys), i, _shorten(p)))
                    i += 1
        if not cand:
            out[did] = [plain(segs[0].get("en", ""))] if segs else []
            continue
        cand.sort(key=lambda x: (-x[0], x[1]))
        top = cand[:GOAL_N]
        out[did] = [c[2] for c in sorted(top, key=lambda x: x[1])]
    return out


def render_part2(blocks, hand=None):
    buckets, cur = {}, None
    for b in blocks:
        if b["type"] == "day":
            cur = b["id"]
            buckets[cur] = []
        elif cur:
            buckets[cur].append(b)
    goals = day_goals(blocks, hand)
    out = ['''<section id="part2">
  <h2><span class="num">Part 2</span>逐句精听<span class="opt">必学 · 分 3 天</span></h2>''']
    for b in blocks:
        if b["type"] == "day":
            items = [g for g in goals.get(b["id"], []) if g]
            g = "".join('<b>%s</b>　' % x for x in items)
            out.append('''  <div class="day" id="%s">
    <div class="d">%s</div>
    <div class="goal">今日只掌握 %d 句：%s</div>
    <label class="chk"><input type="checkbox" data-day="%s"> 说过了，打勾</label>
  </div>''' % (b["id"], b["t"], len(items), g.strip(), b["id"]))
        else:
            out.append(render_seg(b))
    out.append("</section>")
    return "\n\n".join(out)


BAND_CLS = {"A": "a", "B": "b", "C": "c", "D": "d"}
TH = '<thead><tr><th class="mark">收藏</th><th style="width:26%">单词</th><th style="width:28%">音标（美）</th><th>释义</th><th class="mark">打卡</th></tr></thead>'


def render_part3(bands):
    out = ['''<section id="part3">
  <h2><span class="num">Part 3</span>学词汇<span class="opt">重点 · 可打卡收藏</span></h2>
  <div class="maskbar">
    <span class="lb">自测：</span>
    <button class="tbtn" data-mask="en">🙈 遮英文 + 音标</button>
    <button class="tbtn" data-mask="zh">🙈 遮中文</button>
    <span class="lb">（点一下表格里那一行可以单独看答案）</span>
  </div>''']
    for b in bands:
        cls = BAND_CLS.get(b["band"], "a")
        rows = []
        for r in b["rows"]:
            rows.append(
                '      <tr><td class="mark"><button class="star" data-id="%s" data-en="%s" data-zh="%s">☆</button></td>'
                '<td><button class="spk" data-say="%s" title="听发音">🔊</button>%s</td>'
                '<td class="ipa">%s</td><td>%s</td>'
                '<td class="mark"><input type="checkbox" class="fx" data-id="%s"></td></tr>'
                % (r["id"], r["en"], r["zh"], r["en"], r["en"], r["ipa"], r["zh"], r["id"]))
        # A 档（最常用）默认展开；B/C/D 默认折叠，点标题条展开，避免一上来就是压力
        if b["band"] == "A":
            out.append('\n  <div class="band %s">%s</div>' % (cls, b["title"]))
            tcls = "vt"
        else:
            out.append('\n  <div class="band %s tog"><span>%s</span>'
                       '<span class="fold-hint" data-t="点开看 %d 个">点开看 %d 个 ▸</span></div>'
                       % (cls, b["title"], len(rows), len(rows)))
            tcls = "vt folded"
        out.append("  <table class=\"%s\">\n    %s\n    <tbody>\n%s\n    </tbody>\n  </table>" % (tcls, TH, "\n".join(rows)))
    out.append("</section>")
    return "\n".join(out)


def render_part4(groups):
    out = ['''<section id="part4">
  <h2><span class="num">Part 4</span>学句子<span class="opt">最重要 · 妈妈可以直接说</span></h2>
  <p style="color:var(--muted);font-size:14.5px">这些是<strong>你对宝宝说的话</strong>，不是博主的旁白。先挑 2 句今天就用起来。</p>''']
    for g in groups:
        out.append('\n  <div class="grp">%s</div>\n  <div class="slist">' % g["g"])
        for r in g["rows"]:
            out.append(
                '    <div class="srow"><button class="star" data-id="%s" data-en="%s" data-zh="%s">☆</button>'
                '<div class="tx"><div class="e"><button class="spk" data-say="%s" title="听发音">🔊</button>%s</div>'
                '<div class="c">%s</div></div>'
                '<input type="checkbox" class="fx" data-id="%s"></div>'
                % (r["id"], r["en"], r["zh"], r["en"], r["en"], r["zh"], r["id"]))
        out.append("  </div>")
    out.append("</section>")
    return "\n".join(out)


def render_part5(items):
    out = ['''<section id="part5">
  <h2><span class="num">Part 5</span>练一练<span class="opt">中译英 / 开口说</span></h2>
  <p style="color:var(--muted);font-size:14.5px">题目只考前面出现过的东西。先自己说一遍，再看答案。</p>''']
    for i, q in enumerate(items, 1):
        opts = ('\n    <div class="opts">%s</div>' % q["opts"]) if q.get("opts") else ""
        out.append('''  <div class="q"><div class="qh"><span class="kind">%d · %s</span>%s</div>%s
    <div class="ans"><button>看答案</button><div class="body">%s</div></div></div>'''
                   % (i, q["kind"], q["q"], opts, q["ans"]))
    out.append("</section>")
    return "\n\n".join(out)


def render_part6(p6):
    rows = "\n".join("      <tr><td>%s</td><td><strong>%s</strong></td><td>%s</td></tr>" % tuple(r) for r in p6["rows"])
    card = ""
    if p6.get("card"):
        card = '\n  <div class="card">\n    <div style="font-weight:700;margin-bottom:5px">%s</div>\n    <p style="margin:0;font-size:14.5px">%s</p>\n  </div>' % (p6["card"]["t"], p6["card"]["body"])
    return f'''<section id="part6">
  <h2><span class="num">Part 6</span>避开中式英语</h2>
  <p style="color:var(--muted);font-size:14.5px">{p6["lead"]}</p>
  <table>
    <thead><tr><th style="width:30%">这样说不太自然</th><th style="width:32%">母语者更常说</th><th>为什么</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table>{card}
</section>'''


def render_part7(tips):
    out = ['<section id="part7">\n  <h2><span class="num">Part 7</span>文化贴士<span class="opt">选学</span></h2>']
    for t in tips:
        fig = ""
        if t.get("fig"):
            fig = '\n    <figure>\n      <img src="%s" alt="%s">\n      <figcaption>%s</figcaption>\n    </figure>' % (t["fig"][0], t["fig"][1], t["fig"][1])
        out.append('\n  <div class="tip">\n    <div class="th">%s</div>\n    <p>%s</p>%s\n  </div>' % (t["t"], t["p"], fig))
    out.append("</section>")
    return "\n".join(out)


CONTACT = '''  <div class="contact">
    <div class="t">关注我</div>
    <div>📕 小红书：一只小粽粽（156328444）</div>
    <div>🎵 抖音：一只小粽粽（779921861）</div>
    <div>💬 微信：Ivanna-62</div>
    <div>📧 ivanna000@foxmail.com</div>
  </div>'''


def render_footer(d):
    lines = [d["disclaim_src"]]
    if d.get("disclaim_mid"):
        lines.append(d["disclaim_mid"])
    lines.append("打卡与收藏记录保存在本机浏览器里，不上传、不同步；可在复习清单里导出存档。")
    body = "<br>\n    ".join(lines)
    return '''<footer id="me">
%s
  <div class="disclaim">
    %s
  </div>
</footer>''' % (CONTACT, body)


def load_hand_goals(slug):
    """tools/goals.json 里可以手写覆盖某课的 Day 目标（自动挑得不理想时用）"""
    p = os.path.join(BASE, "goals.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8")).get(slug)
    except Exception:
        return None


def build(d):
    global SLUG
    SLUG = d.get("slug", "")
    tips = d.get("part7") or []
    skip = () if tips else ("part7",)      # 没有真文化内容的课，整节不出现
    hand = load_hand_goals(SLUG)
    blocks = [
        render_hero(d),
        "<!-- ===== 怎么用 ===== -->\n" + render_how(d),
        "<!-- ===== Part 1 全篇原声 ===== -->\n" + render_part1(d["part1"]),
        "<!-- ===== Part 2 逐句精听 ===== -->\n" + render_part2(d["part2"], hand),
        "<!-- ===== Part 3 词汇表 ===== -->\n" + render_part3(d["part3"]),
        "<!-- ===== Part 4 场景常用句 ===== -->\n" + render_part4(d["part4"]),
        "<!-- ===== Part 5 练习 ===== -->\n" + render_part5(d["part5"]),
        "<!-- ===== Part 6 避免中式英语 ===== -->\n" + render_part6(d["part6"]),
    ]
    if tips:
        blocks.append("<!-- ===== Part 7 文化贴士 ===== -->\n" + render_part7(tips))
    blocks.append(render_footer(d))
    body = "\n\n".join(blocks)
    brand = ('<a class="home" href="../index.html">← 系列目录</a>%s<small>%s</small>' % (d["brand_zh"], d["en"]))
    html = (SHELL
            .replace("__TITLE__", d["title_tag"])
            .replace("__BRAND__", brand)
            .replace("__TOC__", render_toc(skip))
            .replace("__BODY__", body)
            .replace("__KEY_CHECK__", d["key_check"])
            .replace("__KEY_FAV__", d["key_fav"])
            .replace("__SLUG__", d["slug"])
            .replace("__LESSON_CN__", d["lesson_cn"]))
    outdir = os.path.join(ROOT, "outputs", "亲子英语", d["slug"])
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "index.html")
    io.open(path, "w", encoding="utf-8").write(html)
    left = [t for t in ("__TITLE__", "__BRAND__", "__TOC__", "__BODY__", "__KEY_CHECK__",
                        "__KEY_FAV__", "__SLUG__", "__LESSON_CN__") if t in html]
    print("written", path, len(html), "chars; part7=%s; leftover tokens: %s"
          % ("on" if tips else "off", left or "none"))
    return path


if __name__ == "__main__":
    src = sys.argv[1]
    if not os.path.isabs(src):
        src = os.path.join(ROOT, src)
    d = json.load(io.open(src, encoding="utf-8"))
    build(d)
