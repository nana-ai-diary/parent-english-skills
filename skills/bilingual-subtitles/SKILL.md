---
name: bilingual-subtitles
description: 用ffmpeg drawtext+drawbox烧制中英双语字幕（带半透明遮罩背景），并拼接片尾预设视频。当需要给视频加双语字幕、字幕叠加、带背景的文字字幕时使用。包含whisper时间轴校准、安全区域规则和预设视频拼接。Burn bilingual (EN+CN) subtitles with semi-transparent background mask using ffmpeg drawtext+drawbox, then append preset outro video. Use when adding bilingual subtitles, subtitle overlays, or text captions with background to video.
version: 2.1.0
---

# Bilingual Subtitle Burner

Burn bilingual subtitles (English + Chinese) into video with semi-transparent background mask using ffmpeg `drawtext` + `drawbox` filters. After rendering, append the preset outro video to the end.

## When to Use

- Adding bilingual (EN+CN) hard subtitles to video
- Burning subtitles with semi-transparent background mask
- Any subtitle overlay requiring precise timing alignment with audio
- Videos targeting mobile platforms (safe area compliance)

---

## Preset Outro Video（默认必做 / MANDATORY）

> **用户明确要求（2026-09-26）：每次都必须在成片末尾拼接「关注我」片尾视频，不要省略。**
> 早期加固版曾把它降级为「默认不拼接」，导致交付时漏掉片尾，用户只能自己补。**已恢复为默认必做。**

**默认行为：必须拼接。** 执行流程：

1. 读配置文件 `~/.workbuddy/skills/parent-english.config.yaml` 的 `preset_video` 字段
   （安装后在配置里填你的片尾视频路径；典型规格约 1.4s / 1920×1080 / 30fps）。
2. 字段非空且文件存在 → **烧完字幕后必须执行 Step 7 追加**，交付的就是带片尾的最终版。
3. 字段为空或文件不存在 → **不要静默跳过**，先问用户片尾视频路径；拿到路径后照 Step 7 执行。
   只有用户明确说「这条不要片尾」时才跳过，并在交付说明里注明。

片尾内容通常是「欢迎关注我」一类的引导卡。拼接前确认文件可正常播放即可，不必逐帧核对。

---

## Why NOT moviepy

**moviepy's TextClip has a fatal flaw**: it generates text images with **0px bottom padding**. Text content extends to the very last pixel row, causing descenders (g, y, p) and CJK bottom strokes to appear clipped when composited. No amount of LINE_SPACING or MARGIN tweaking reliably fixes this without visible artifacts.

**ffmpeg drawtext renders directly on video frames** — no intermediate image generation, no clipping, no workarounds needed. Combined with `drawbox` for the background mask, this produces clean, professional results.

---

## Step 0（强烈推荐）: 视频自带硬字幕歌词时，先提取校对文本

音乐视频 / 儿歌视频常在底部有烧死的歌词条。**当它与音频一致时**，它是最权威的文本来源，Whisper 听歌时会把歌词听错（例：`Moon cakes, moon cakes are round` 被听成 `Moon kicks, moon kicks around`），甚至在器乐段凭空编造整句歌词。先做这一步可以避免全部这类错误。

> ⚠️ **前提：先确认硬字幕和音频是同一套话**。实测有片子的烧屏字幕是「演示者第一人称台词」，
> 而音轨是「给家长的第三人称教学口播」，两套词完全不同、时间轴也对不上。
> **别把硬字幕当权威文本直接抄**——验证方法见 Pitfall 21（VAD + initial_prompt 对数概率 + 局部窗口）。
> 没有验证过就按硬字幕去"修正" Whisper 结果，会把整篇字幕改错。

```bash
# 1) 先定位歌词条：抽几帧手动看一眼，确定 y 偏移（1080p 常见 y≈966, h≈100）
ffmpeg -y -ss 75 -i SRC.mp4 -vframes 1 -vf "crop=1920:120:0:960" probe.png

# 2) 按 1fps 拉出整条歌词带，裁到正文区域
ffmpeg -y -i SRC.mp4 -vf "fps=1,crop=1920:90:0:972" band/%03d.png
```

然后用 PIL 把若干帧纵向拼成「对照长图」，直接肉眼读（对多模态模型来说 OCR 成本高于直接看图）：

```python
from PIL import Image, ImageDraw, ImageFont
files = sorted(glob.glob("band/*.png"))
font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 34)
ROWS = 10
for page in range(0, len(files), ROWS):
    c = Image.new("RGB", (1920, 100*ROWS), (20, 20, 20)); d = ImageDraw.Draw(c)
    for r, f in enumerate(files[page:page+ROWS]):
        c.paste(Image.open(f).crop((0, 0, 1920, 100)), (0, r*100))
        d.text((6, r*100+2), f"{page+r+1}", font=font, fill=(255, 0, 0))  # 帧号 = 秒数+1
    c.save(f"sheets/sheet_{page//ROWS:02d}.png")
```

**帧号换算坑**：`fps=1` 的第 N 张图 = `t = N-1` 秒（不是 N 秒）。拼图标签若写成 `i+1`，读图时要减 1，否则整条时间轴会偏移 1 秒。

**歌词行切换时刻**也可以用同一批帧算出来：对每帧取「文字墨迹」在水平方向的投影（宽度剖面），相邻帧剖面差异骤增处即换行点。但卡拉OK 逐字高亮会让剖面每 0.2s 抖一次，需要更高的阈值，或者干脆只用来交叉验证 Whisper 的边界。

## Complete Workflow


### Step 0.5（必做）: 先建「字幕完整性清单」，别挑金句

> 2026-11-06 补：**硬字幕不是「精选句子」任务**。除非用户明确说只要高亮片段，
> 否则必须覆盖视频里每一句听得见的英文。`video-english-xhs` 挑 8–10 句做正文是对的，
> 但那是从完整清单里挑，不是让硬字幕只烧这 8–10 句。

烧录前先写一份 `subtitle_manifest.csv`（或 `.md`），一句一行：

```text
start | end | english | chinese | source | status | notes
```

素材来源全部用上：Whisper 词级时间戳、已有 SRT/VTT/JSON、用户给的修正、
低置信/嘈杂区间的人工复听。

规则：
- 不要因为「不是教学重点」就丢掉短反应、语气词、确认句、重复句
  （`Okay.` / `See?` / `Yummy!` / `Whoa!`）。
- 相邻但属于不同说话人的轮次不要合并。
- 不要用更顺的「教学表达」替换原片措辞。
- 不确定的行**保留**并标 `needs_review`，写明时间区间与原因，不要静默删掉。
- 用户给的修正视为权威；若与音频冲突，在审计里记录冲突点。

### Step 1: Transcribe with Whisper (word-level timestamps)

```python
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.wav", language="en", word_timestamps=True)

for seg in segments:
    for w in seg.words:
        print(f"  {w.word:20s} {w.start:.2f} -> {w.end:.2f}")
```

**CRITICAL**: Use `word_timestamps=True` and align subtitle start/end to individual word boundaries, NOT segment boundaries. Segment-level timing can be off by 2-3 seconds.

### Step 2: Build Subtitle Entries with Corrected Timing

For each subtitle, set:
- **start** = first word's `start` time
- **end** = last word's `end` time
- **gap-fill**: extend each entry's `end` to the next entry's `start` (eliminates blank gaps)

```python
SUBS = [
    (0.00, 2.12,   "Hi friends! In this video", "小朋友们好！这个视频"),
    (2.12, 7.38,   "we are going to be coloring shapes. Let's begin!", "我们要给图形涂色。开始吧！"),
    # ... each entry's end = next entry's start
]
```


### Step 2.5（默认 / MANDATORY）: 一屏一句，绝不折行

> 用户 2026-11-04、11-06 两次确认：**尽量一屏就一句，不要折行**。
> 但「一句」指的是**语义完整的句子**，不是「按字符数切出来的一截」。
> 机械按字符数硬切会切出 `big audiences.` / `fun and fast.` 这种一两个词的尾巴屏，
> 用户明确反对（「下一屏也就一两个词，分开没必要」）。

#### 铁律：按真实像素宽度判断，不按字符数

字符宽窄差很多（`mmmm` 与 `iiii` 同样 4 字符，宽度差一倍以上）。必须用
`PIL.ImageFont.getlength()` 量实际宽度，字体/字号要与 `drawtext` 完全一致：

```python
from PIL import ImageFont
FEN = ImageFont.truetype(FONT_PATH, 62)   # 与 drawtext 同一字体、同一字号
FCN = ImageFont.truetype(FONT_PATH, 60)
LIM = 1800          # VW - 120px 边距（1920 宽）
MIN_WORDS = 3       # 每行至少 3 词，杜绝 1–2 词孤儿屏

def en_w(s): return FEN.getlength(s)
```

规则（按顺序执行）：

1. **整句 `en_w(sentence) <= LIM` → 整句一屏，不拆。** 62px 加粗雅黑下
   40+ 字符的句子常常仍能一行放下（实测 `It's a style of dance that's fun and fast.`
   = 1211px，`and we'd perform in front of big audiences.` = 1358px）。
   实测一支 32 句独白里 **22 句本来就放得下**（最宽 1768px），别误切。
2. 只有真的超宽才拆，且拆成**多条独立字幕条目**（各自独占一屏），不是把一条字幕排成多行。
   用 DP 求最少行数 + minimax 让各行宽度尽量接近 + 每行 ≥ `MIN_WORDS` 词 + 每行 ≤ `LIM`。
3. 中文译文同样用 `FCN.getlength(cn) <= LIM` 校验；超了就精简译文，不给中文折行。
   拆出来的每一屏仍显示**完整中文译文**（重复），保证每屏信息自洽。
4. 均衡切点偶尔会切断固定搭配（`lots of popping and locking`、`the different dance moves`）
   → 用 `OVERRIDE` 按句序号手工指定切点；优先在句号 / 逗号后切。
5. **布局固定单行**：EN `y=910`、CN `y=988`、`box_y=886`、`box_h=VH-box_y`（≈194px）。
   不要为长句堆叠多行 drawtext、也不要动态改遮罩高度 —— 长句已经拆成多条字幕了。
6. 句内拆出的多屏，按各行**字符数比例**分配该句 `[首词start, 末词end]` 的时间；
   屏与屏之间做 gap-fill（上限 ~2.5s；长静音不强行延续，避免 `Whoa!` 挂屏 5 秒）。
7. 相邻字幕用 `end - 0.03` 收尾（见 Step 4），避免边界帧重叠出重影。

可直接复用的实现（含宽度断言，超宽 / 孤儿行会在烧录前直接报错）：

```python
def norm_words(words):
    """Repair ASR word-level artifacts, e.g. 'hip -hop' -> 'Hip-hop'."""
    s = " ".join(w.strip() for w in words)
    s = s.replace("hip -hop", "Hip-hop")
    return s.split(" ")

def balance_cuts(words):
    """Fewest rows, each <= LIM, widths balanced, >= MIN_WORDS words per row."""
    n = len(words)
    wid = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        for j in range(i + 1, n + 1):
            wid[i][j] = en_w(" ".join(words[i:j]))
    if wid[0][n] <= LIM:
        return [(0, n)]                     # whole sentence fits -> 1 screen
    INF = float("inf")
    for K in range(2, 7):
        dp = [[INF] * (n + 1) for _ in range(K + 1)]
        par = [[-1] * (n + 1) for _ in range(K + 1)]
        dp[0][0] = 0.0
        for k in range(1, K + 1):
            for j in range(1, n + 1):
                for i in range(0, j):
                    if j - i < MIN_WORDS or wid[i][j] > LIM or dp[k-1][i] == INF:
                        continue
                    v = max(dp[k-1][i], wid[i][j])   # minimax -> balanced rows
                    if v < dp[k][j]:
                        dp[k][j] = v; par[k][j] = i
        if dp[K][n] < INF:
            cuts = [n]; j = n
            for k in range(K, 0, -1):
                cuts.append(par[k][j]); j = par[k][j]
            cuts = cuts[::-1]
            return [(cuts[t], cuts[t+1]) for t in range(K)]
    return [(0, n)]

OVERRIDE = {}     # {sentence_index: [word_cut_positions]} for semantic integrity

disps = []        # [start, end, en_text, cn_text]，一条 = 一屏
for si, (a, b, en, cn) in enumerate(SUBS):
    wds = words_of(a, b)                       # 该句的词级时间戳
    words = norm_words([w["word"] for w in wds])
    s0 = min(w["start"] for w in wds); s1 = max(w["end"] for w in wds)
    if si in OVERRIDE:
        pts = [0] + OVERRIDE[si] + [len(words)]
        ranges = [(pts[i], pts[i+1]) for i in range(len(pts) - 1)]
    else:
        ranges = balance_cuts(words)
    for i, j in ranges:
        assert en_w(" ".join(words[i:j])) <= LIM, f"EN too wide @{si}"
        assert j - i >= MIN_WORDS, f"orphan row @{si}"
    assert FCN.getlength(cn) <= LIM, f"CN too wide @{si}"
    lens = [len(" ".join(words[i:j])) for i, j in ranges]
    total = sum(lens) or 1; acc = 0.0
    for (i, j), L in zip(ranges, lens):
        t0 = s0 + acc / total * (s1 - s0); acc += L
        t1 = s0 + acc / total * (s1 - s0)
        disps.append([t0, t1, " ".join(words[i:j]), cn])
```

**实测对比（舞者.mp4，162s，32 句）**：按 32 字符硬切 = 72 条、出现 1–2 词尾巴屏；
按本规则 = **43 条**（22 句整句一屏 + 10 句均衡拆 2–3 屏），最短行 3 词、
最长行 1768px，零折行、零裁切。改动前先跑宽度断言再烧，别靠肉眼。

### Step 2.6（必做）: 渲染前做覆盖审计

写 `subtitle_coverage_audit.md`：

```text
Expected lines: <manifest 条数>
Rendered SUBS: <实际条数（拆屏后 disps 条数）>
Missing required lines: <count>
Needs-review lines: <count>
```

再列一张表 `time | expected English | SUBS index | status | note`，状态用
`included` / `missing` / `needs_review` / `skipped_by_request`。
**有 `missing` 就停下来修，不许带病渲染**；有 `needs_review` 要在交付说明里点名。
注意 Step 2.5 会把一句拆成多屏，审计按「句子」计数，不要按屏数对 manifest。

### Step 3: Create Text Files (fixes apostrophe escaping)

**CRITICAL**: ffmpeg drawtext `text` parameter cannot handle straight apostrophes `'` (they break filter parsing). Use `textfile` parameter instead — write each subtitle's text to individual `.txt` files.

```python
for i, (start, end, en, cn) in enumerate(SUBS):
    with open(f"txt/en_{i:03d}.txt", "w", encoding="utf-8") as f:
        f.write(en)    # Let's stays as Let's — no escaping needed
    with open(f"txt/cn_{i:03d}.txt", "w", encoding="utf-8") as f:
        f.write(cn)
```

### Step 4: Build ffmpeg Filter Chain

```python
VW, VH = 1920, 1080

# ---- 默认走「大字 + 大遮罩」档（用户 2026-09-24 / 09-26 两次确认的偏好）----
# 括号内是 2.0 之前的旧值，只有在用户明确要「小一点」时才回退
EN_FONTSIZE = 62        # (42) 用户要求「字体大一点」
CN_FONTSIZE = 60        # (42)
LINE_GAP = 16           # (10)
SAFE_BOTTOM = 32        # (20) CN text bottom edge distance from video bottom
BOX_PAD_Y = 24          # (16) vertical padding inside mask
# 遮罩不透明度：原片底部已烧硬字幕 → 1.0 全不透明（见 Pitfall 13）；
#   无硬字幕但底部是大面积亮色/频道水印 → 0.92；无硬字幕且底部本身就暗 → 0.86
BOX_OPACITY = 1.0       # (0.86)
# 上面这组参数 → 遮罩高约 194px（占画面 18%），可完整盖住 1080p 底部硬字幕条（y≈905-1060）

# Layout calculation
cn_y = VH - SAFE_BOTTOM - CN_FONTSIZE   # CN text top
en_y = cn_y - LINE_GAP - EN_FONTSIZE    # EN text top
box_y = en_y - BOX_PAD_Y
box_h = VH - box_y                       # MASK FLUSH WITH VIDEO BOTTOM

filter_parts = []
for i, (start, end, en, cn) in enumerate(SUBS):
    # between() 含两端点；收 0.03s 防止相邻字幕在边界帧重叠出重影
    timing_end = max(start, end - 0.03)
    timing = f"between(t\\,{start}\\,{timing_end})"

    # 1. Background mask (full width, flush with bottom)
    filter_parts.append(
        f"drawbox=x=0:y={box_y}:w={VW}:h={box_h}"
        f":color=black@{BOX_OPACITY}:t=fill"
        f":enable='{timing}'"
    )
    # 2. English text (yellow)
    filter_parts.append(
        f"drawtext=fontfile='{esc_path(FONT_PATH)}'"
        f":textfile='{esc_path(en_txt_path)}'"
        f":fontsize={EN_FONTSIZE}"
        f":fontcolor=0xFFD700"
        f":borderw=2:bordercolor=black"
        f":x='(w-text_w)/2'"
        f":y={en_y}"
        f":enable='{timing}'"
    )
    # 3. Chinese text (white)
    filter_parts.append(
        f"drawtext=fontfile='{esc_path(FONT_PATH)}'"
        f":textfile='{esc_path(cn_txt_path)}'"
        f":fontsize={CN_FONTSIZE}"
        f":fontcolor=white"
        f":borderw=2:bordercolor=black"
        f":x='(w-text_w)/2'"
        f":y={cn_y}"
        f":enable='{timing}'"
    )
```

### Step 5: Write Filter to File and Render

```python
# Write filter to file (avoids Windows command-line length limit)
with open("filter.txt", "w", encoding="utf-8") as f:
    f.write(','.join(filter_parts))

# Render
ffmpeg -y -i input.mp4 \
    -filter_script:v filter.txt \
    -c:v libx264 -preset medium -crf 23 \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    subtitled.mp4
```

### Step 6: Verify Subtitle Render

```bash
# Extract frames at key timestamps
ffmpeg -y -i subtitled.mp4 -ss 2 -vframes 1 -q:v 2 frame_2s.png
ffmpeg -y -i subtitled.mp4 -ss 30 -vframes 1 -q:v 2 frame_30s.png
ffmpeg -y -i subtitled.mp4 -ss 60 -vframes 1 -q:v 2 frame_60s.png
```

Visually inspect each frame for:
- Text fully visible (no clipping)
- Mask flush with video bottom
- Subtitle matches audio at that timestamp
- Apostrophes render correctly as straight `'` not curly `'`

### Step 7: Append Outro Video（默认必做 / MANDATORY）

**每次都要执行**，详见顶部「Preset Outro Video」一节。只有用户明确说不要片尾时才跳过。

```python
# 从配置读取；配置为空时先问用户，不要直接置 None 就跳过
PRESET_VIDEO = read_config()["preset_video"]   # e.g. r"C:\...\亲子视频-定稿\预设.mp4"
```

**先把预设片尾重编码成与正片一致的规格，再 concat**（实测两个坑，都会产出「看起来成功但时长/音画不对」的坏文件）：

| 不一致项 | 症状（实测） | 要求 |
|----------|--------------|------|
| **音频采样率不同**（preset 48k vs 正片 44.1k） | 最终 duration 变成 **136.3s** 而不是 125.2s —— 正片音轨被按 48/44.1 拉伸了约 11s，音画错位 | preset 音频必须 resample 成正片的采样率 |
| 视频 codec 不同（preset HEVC vs 正片 H.264） | `-c copy` 侥幸能拼，但 MP4 里混合 codec，部分播放器/平台会花屏或拒绝播放 | preset 视频转成 H.264 |

先 probe 正片拿到目标采样率，再重编码 preset：

```bash
# 1) 取正片的音频采样率（本机这支是 44100）
ffprobe -v error -select_streams a:0 -show_entries stream=sample_rate \
        -of default=nw=1:nk=1 subtitled.mp4

# 2) 把「关注我」片尾重编码成 H.264 + AAC@目标采样率（-ar 必须与正片一致！）
ffmpeg -y -i preset.mp4 \
    -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 \
    -c:a aac -b:a 192k -ar 44100 -ac 2 \
    -movflags +faststart preset_h264.mp4
```

再用 concat demuxer 拼（`-c copy`，秒级完成，不二次压缩正片）：

```python
import subprocess, os, tempfile, shutil

# concat list 里的路径含中文时可能出问题：把重编码后的片尾复制成 ASCII 临时名再拼
tmp_dir = tempfile.gettempdir()
tmp_preset = os.path.join(tmp_dir, "preset_ascii.mp4")
shutil.copyfile(preset_h264, tmp_preset)

# 1. Create concat list file
concat_list = os.path.join(tmp_dir, "concat_list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    f.write(f"file '{os.path.abspath(subtitled_mp4)}'\n")
    f.write(f"file '{tmp_preset}'\n")

# 2. Concatenate（-c copy，秒级完成，不二次压缩正片）
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c", "copy",
    "-movflags", "+faststart",
    output_final_mp4
], check=True)

# 3. Sanity check: 最终时长 ≈ 正片时长 + 片尾时长（误差 <0.5s）
#    ffprobe -v error -show_entries format=duration -of default=nw=1 final.mp4
```

**IMPORTANT**: If the preset video has different resolution/codec/fps from the subtitled video, you must re-encode one of them to match before concatenation, or use the filter-based concat method:

```bash
ffmpeg -y -i subtitled.mp4 -i preset.mp4 \
    -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]" \
    -map "[outv]" -map "[outa]" \
    -c:v libx264 -preset medium -crf 23 \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    final_output.mp4
```

---

## Windows Path Escaping

ffmpeg filter parameters use `:` as separator and `\` as escape character. Windows paths like `C:\Windows\Fonts\msyh.ttc` MUST be escaped:

```python
def esc_path(p):
    """C:\\Windows\\Fonts\\msyh.ttc -> C\\:\\\\Windows\\\\Fonts\\\\msyh.ttc"""
    return p.replace('\\', '\\\\').replace(':', '\\:')
```

---

## Key Parameters

### Font (must support CJK)

| Platform | Font Path | Font Name |
|----------|-----------|-----------|
| Windows | `C:\Windows\Fonts\msyh.ttc` | Microsoft YaHei |
| Windows（粗体，视频上更清晰，推荐） | `C:\Windows\Fonts\msyhbd.ttc` | Microsoft YaHei Bold |
| macOS | `/System/Library/Fonts/STHeiti Medium.ttc` | STHeiti |
| Linux | `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` | WenQuanYi |

### Font Size by Resolution

**默认档 =「大字 + 大遮罩」**（用户 2026-09-24 起两次确认的偏好，除用户明确要小字外一律用它）：

| Resolution | Font Size | LINE_GAP | SAFE_BOTTOM | BOX_PAD_Y | 遮罩高 |
|------------|-----------|----------|-------------|-----------|--------|
| **1920×1080（默认）** | **EN 62 / CN 60** | **16px** | **32px** | **24px** | **≈194px（18%）** |
| 1280×720 | 32px | 8px | 20px | 16px | ≈110px |
| 1920×1080（旧小字档） | 42px | 10px | 20px | 16px | ≈148px |
| 3840×2160 | 84px | 20px | — | — | — |

大字档能完整盖住原片底部的歌词条 / 关键词卡（1080p 实测硬字幕落在 y≈905-1060）。
宽度自检：`ImageFont.getlength(text)` 最大值应 < `VW - 120`（62px 拉丁字符约可放 34 个）。

### Safe Area (Mobile Compliance)

- **SAFE_BOTTOM**: Distance from video bottom to CN text bottom edge
  - 20px: mask flush, suitable for most platforms
  - 40-60px: extra margin for platforms with UI overlays
- **Mask bottom**: Always set `box_h = VH - box_y` to ensure flush with video bottom

### Colors

- English: `0xFFD700` (gold/yellow)
- Chinese: `white`
- Border: `black`, width 2px
- Mask: `black@0.86` (86% opacity) — 原片底部**没有**硬字幕时用这个；
  原片底部**已有**硬字幕时用 `black@1.0`（见 Pitfall 13）

---

## Pitfalls and Lessons Learned

### 1. NEVER use moviepy TextClip for subtitle burning
moviepy generates text images with 0px bottom padding. Descenders and CJK strokes get clipped. Adding transparent padding via numpy vstack introduces visible artifacts. **Use ffmpeg drawtext instead.**

### 2. NEVER use ffmpeg `text=` parameter for text with apostrophes
The `'` character breaks ffmpeg's filter parser (it's a string delimiter). Replacing with curly quotes `\u2019` causes display issues. **Use `textfile=` parameter** — write text to individual .txt files and reference them.

### 3. NEVER use whisper segment-level timestamps for subtitle timing
Segment boundaries can be off by 2-3 seconds from actual speech. **Always use `word_timestamps=True`** and align subtitle start to the first word's `start` time, end to the last word's `end` time.

### 4. ALWAYS gap-fill between subtitle entries
If there's a pause between sentences, extend the previous subtitle's end time to the next subtitle's start time. Otherwise subtitles flash/disappear during pauses. Set each entry's `end = next_entry.start`.

### 5. ALWAYS verify mask is flush with video bottom
Calculate `box_h = VH - box_y` (not based on text height alone). A 4px gap between mask bottom and video bottom looks unprofessional.

### 6. ALWAYS write filter to file on Windows
The filter chain for 40+ subtitles easily exceeds Windows' 8191-character command-line limit. Use `-filter_script:v filter.txt` instead of inline `-vf`.

### 7. ASS filter fails with CJK file paths
The ffmpeg `ass=` filter cannot parse paths containing Chinese characters (it treats them as image size parameters). If the video path contains CJK characters, **use drawtext fallback instead of ASS filter**.

### 8. Bitrate: use CRF or match source
- CRF 23 is a good default (balanced quality/size)
- For bitrate mode: probe source bitrate, set output to ~1.3x source
- `ffprobe -v error -show_entries format=bit_rate -of default=nw=1:nokey=1 input.mp4`

### 9. Concat preset video: match formats before stream copy
If the preset outro video has different resolution, codec, or fps than the subtitled video, `-c copy` concat will produce playback glitches. Either re-encode the preset to match, or use filter-based concat (`concat=n=2:v=1:a=1`).

### 10. 歌曲转录必须双模型交叉验证
Whisper 在唱歌音频上的典型故障是**重复幻觉**：把前面出现过的歌词原样搬到后面的段落（实测 `medium` 把第三段主歌听成了上一段副歌的歌词，`small` 反而正确）。做法：
- 用 `small` 和 `medium` 各跑一遍全片，逐句比对；不一致的区间再用**局部窗口**单独跑一次。
- 局部重跑时给足上下文（前后各留 3~5s），并设 `condition_on_previous_text=False, beam_size=5`。
- 仍然无法判定时，用**音频互相关**：把待判段与已知段落做归一化滑动互相关，0.3 以上的相关值基本可以定性。

### 11. faster_whisper 传 numpy 数组必须是 float32
把 `np.frombuffer(..., np.int16)` 的裸数据直接传给 `transcribe()` 会得到**空结果**（不是报错）。必须先转：

```python
data = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
```

### 12. HF 模型下载：代理 502 时走镜像，并落到本地目录
`WhisperModel("medium")` 触发 `snapshot_download` 时若代理返回 502 会直接失败。绕过办法：

```bash
# hf-mirror 直链下载权重（medium ≈ 1.5GB），config/tokenizer/vocabulary 从已有缓存 copy
curl -L -o $D/model.bin "https://hf-mirror.com/Systran/faster-whisper-medium/resolve/main/model.bin"
```
然后 `WhisperModel(r"D:/models/faster-whisper-medium", ...)` 直接指向目录，不再联网。
注意 `snapshot_download` 走 xet 协议时可能报 `401 Unauthorized`（CAS Client Error），改用上面的 resolve 直链即可。

### 13. 遮罩不透明度要够高，否则原片硬字幕会透出来
若原视频底部已有硬字幕，`black@0.86` 会看到明显的「鬼影」（两套字幕叠在一起）。实测 **0.96 仍有可见残影**（YUV 混合下比理论值亮），要做干净就得用 **`black@1.0` 全不透明**。判断标准：抽帧放大看遮罩区，`max` 只应来自你自己的字幕文字。

**没有硬字幕也可能需要抬不透明度：底部大面积亮色 / 频道水印时同理**（2026-09-29 实测）。
「系扣子&解扣子」原片底部**无任何烧死字幕**（93 帧底带扫描 0 命中），但底部是大面积亮黄桌面
+ 右下角 `Smile and Learn` 水印。按规则本该用 0.86，实测却清晰透出桌面与水印（像脏了一块）。
**量化判据**（渲染前用一行 ffmpeg 就能测，比肉眼可靠）：

```bash
for op in 0.86 0.92 1.0; do
  ffmpeg -y -ss <有代表性的一帧时间> -i SRC.mp4 -vframes 1 \
    -vf "drawbox=x=0:y=<BOX_Y>:w=1920:h=<BOX_H>:color=black@$op:t=fill" _op_$op.png
done
# 再统计 _op_*.png 遮罩区（避开文字行）的灰度均值/最大值
```

实测 0.86 → 均值 21 / 最大 34（肉眼可见鬼影）；0.92 → 均值 11.8 / 最大 19（肉眼近黑）；
1.0 → 全黑。**均值 ≤15 时观感就是「黑底」**，所以亮底场景取 **0.92** 比 0.86 稳，
也不必为了去水印直接跳到纯黑。水印若压在遮罩区正中间，另可考虑裁切或整体上移字幕块。

**原片硬字幕的定位与复验（黄字关键词 / 歌词条通用）**：
- 定位：按 1fps 抽 `crop=1920:150:0:930` 的底带，逐帧统计黄色像素行范围（`r>190 & g>150 & b<130`），
  得到硬字幕的 y 区间（实测两支片子分别落在 905-940 / 956-1045）。**遮罩 `box_y` 必须在这条带的上沿之上**。
- 复验：渲染完成后抽帧统计「自己 EN 行以下」的黄色像素数，应当为 0。
  ⚠️ 我自己的 EN 字幕就是黄色 `0xFFD700`，所以统计区间要避开 EN 文字行（如 EN 占 y 908-976 时，只统计 y 976-1080），
  否则会把自家文字算成残留。
- 何时不要盖：若原片硬字幕是**关键词/单词卡**这类「补充信息」而非重复内容，盖掉会损失教学信息。
  此时应把双语字幕块整体上移（遮罩改成不贴底的中段条带），让原关键词露在下面——务必先问用户或交付时明确提示。

### 14. 长句拆分：按像素宽度 + 均衡 DP，绝不能按字符数硬切
先用 `ImageFont.getlength()` 量出**实际像素宽度**判断是否真的超框（1920 宽留 120px 边距，`LIM=1800`），再用 Whisper 词级时间戳找自然停顿点。完整规则见 **Step 2.5**。

⚠️ 2026-11-06 实测踩过的坑：曾按「每行 32 个字符」硬切，结果把
`and we'd perform in front of big audiences.`（1358px，一行放得下）、
`It's a style of dance that's fun and fast.`（1211px）这类整句切碎，
末屏只剩 `big audiences.` / `fun and fast.` 一两个词 —— 用户明确反对。
**字符数不是宽度**：同样 4 字符 `mmmm` 与 `iiii` 宽度差一倍。
正解是整句优先 + 超宽才用均衡 DP 拆成多条独立字幕（每行 ≥3 词）。
交付前把生成的 `en_*.txt` 全量打印通读一遍，确认没有「孤儿屏」。

### 15. 不确定的短促过门句：宁可用 gap-fill 延续上一句
歌里常有 0.5~1s 的口白/气口（两个模型给出完全不同的内容）。**不要凭猜测新增一行字幕**，直接按 gap-fill 让上一句延续到下一句开始即可；同时要在交付说明里点出这个位置。

### 16. 交付的 .srt 绝对不要和成片 mp4 同目录同名（会造成「双重字幕」）
`成片.mp4` + `成片.srt` 放在同一个文件夹 → VLC / PotPlayer / MPC / 多数播放器与预览面板会**自动加载同名 srt 并叠在硬字幕之上**，用户看到的就是「字幕重影/双重」：
上下两套文本内容一样、位置错开几十像素、一套带黑底一套不带。用户会以为是你烧坏了。

- **交付做法**：srt 放到子目录（如 `subtitle_work/srt_only/成片.srt`），或改名成不匹配 mp4 主名的名字（如 `成片.双语字幕备份.srt`）。
- **排障三步**（判断是「文件被烧重了」还是「播放器叠了一层」）：
  1. `ffmpeg -i 成片.mp4 -vf fps=1 -q:v 3 scan/%03d.jpg` 抽全片帧；
  2. 检查「自己最后一行字幕以下」的行（例如 CN 底部 = `VH - SAFE_BOTTOM`）是否**纯黑**：若为纯黑就是干净的，说明多出来的那层来自外部；
  3. 再抽同时间点的 `ffmpeg -ss T -i 原片.mp4` 帧对比：原片硬字幕应完全被遮罩盖掉。
  另外注意原片硬字幕条的位置（可用紫色/亮度行剖面定位）：它必须整体落在遮罩 `box_y ~ VH` 之内。

### 17. 片尾「关注我」视频必须拼，且预设常是 HEVC
用户要求：**每次交付都要带片尾**，不能因为 SKILL 里写着「可选」就跳过（2026-09-26 漏了一次，用户自己补的）。

- 「关注我」引导卡通常是手机/剪映导出的 **HEVC / 48kHz**，而烧字幕的成片是 **H.264 / 44.1kHz**。
  直接 `-c copy` concat 有两个坑：**采样率不同会把整条正片音轨拉伸**（实测 125.2s 变成 136.3s，多了 11s，
  比例正好是 48000/44100），codec 不同则会产出混合 codec 的 MP4。**必须先把 preset 重编码对齐**（命令见 Step 7）。
- concat list 里写含中文的绝对路径有概率失败 → 把 preset 复制成 ASCII 临时名再写进 list。
- 拼接用 `-c copy`（不二次压缩正片），总耗时几秒；**不要用 filter concat**，那会把整条正片重新编码一遍。
- 交付前 ffprobe 核对：最终 duration ≈ 正片 + 片尾（实测 123.79 + 1.42 → 125.226s，差 0.02s 正常）。
- **预设片尾是 1920×1080 横屏**：正片若为竖屏（612×1080），要先 `crop` 到内容区再 `scale`+`pad` 成同样竖屏尺寸（见下），否则会出现横屏画面被压进竖屏框的怪异效果。
  竖屏实测参数（预设内容 bbox x463-1459 / y102-977）：`crop=1040:900:440:90,scale=612:530:flags=lanczos,pad=612:1080:0:(oh-530)/2:black`。

### 18. 听写结果不合语法时：用 initial_prompt 做对数概率对比，取语法正确的一版并标注
旁白/口播是儿童或不标准发音时，Whisper 会稳定地听出同一个错（两个模型都一致，说明不是随机幻觉）。
实测：`to tie your shoe from you` —— `from` 在语境里讲不通。

判定方法（同一段音频，只换 `initial_prompt`）：

```python
for ip in [None, "to tie your shoe for you", "to tie your shoe from you"]:
    segs, _ = model.transcribe(clip, language="en", beam_size=5, temperature=0.0,
                               condition_on_previous_text=False, initial_prompt=ip)
    for s in segs: print(repr(ip), s.text.strip(), round(s.avg_logprob, 3))
```

无 prompt 时 logprob 更偏向 `from`，但**语法上只可能是 `for`** —— 这类情况按下面的原则取舍：
- 若原片有权威文本（硬字幕/歌词条/官方字幕）→ 以原片为准；
- 否则取**语法正确**的读法，并在交付说明里单列一条「人工修正」，让用户能自己核对。
  反之（把正确的 `for` 写成错的 `from`）在英语学习类内容里是硬伤，绝不可取。

**同理**：品牌名 / 人名以画面中的 logo、水印、片尾卡为准（实测把 `KidSplainer` 听成 `Kidsplanner`）。

**补充：先用「词级 probability」判断是「听错」还是「原文就那样」（2026-10-02 实测）**

`initial_prompt` 对比能告诉你「音频里有没有那句话」，但**判不出「Whisper 听错」还是「说话人本来就那么说」**。
后者要看词级置信度：`word_timestamps=True` 时每个词带 `probability`。

```python
segs, _ = model.transcribe(clip, language="en", beam_size=5, temperature=0.0,
                           condition_on_previous_text=False, word_timestamps=True)
for s in segs:
    for w in s.words:
        print(f"{w.word.strip():<12} p={w.probability:.3f}  {w.start:.2f}-{w.end:.2f}")
```

实测（穿外套，儿童口播）：`put your [coat] into your arm sleeve` 里 `coat` 的 **p=0.993**，
三种 prompt 下 Whisper 都照抄不改 → 说明**声学上确实是这个音**，不是幻觉。

这时是「忠实原音」与「教学正确」的取舍，按下面处理：

| 情形 | 处理 |
|------|------|
| 声学概率低（<0.8）且语义不通 | 按 Pitfall 18 取语法正确读法 |
| **声学概率高（>0.95）但语义不通** | 仍取**语法正确**读法（学习类内容不能教错表达），但交付说明里**必须双向标注**：原始听写 + 采用写法 + 概率值 + 时间点，并说明「想完全忠实原音可一行改回」 |
| 原片有权威文本 | 以权威文本为准，不用管概率 |

本片实例：`put your coat into your arm sleeve`（p=0.993）→ 采用 `put your arm into your sleeve`；
`you put your sleeve nicely through`（p=0.926）→ 采用 `you put your arm nicely through`。
两条都写进了 `subs_data.py` 顶部注释 + 交付说明表格。

### 19. 开烧之前先判断「这个文件是不是已经是我们做的成片」

用户常把交付件**移动**进素材目录并重编号（如 `32.拉拉链.mp4`、`33.系扣子&解扣子 .mp4`）。
如果误当成新素材再烧一遍，新遮罩会叠在旧字幕上 → 旧的中英两行从半透明遮罩里透出来，
变成一块洗不掉的脏影。**这是不可逆的画质损伤，必须先判定再动手。**

判定三件套（一条命令就能跑完，2026-09-29 实测）：

| 判据 | 原片 | 我们的成片 |
|------|------|-----------|
| 视频编码 | 多为 **HEVC**（剪映/手机导出） | **H.264** |
| 时长 | 原始长度 | **≈ 原片 + 片尾 1.416s** |
| 与「原片+1.416」的差 | — | **固定 ≈ +0.0236s**（同一渲染链路的分毫偏差） |

```bash
ffprobe -v error -show_entries format=duration,size \
  -show_entries stream=codec_name -of csv=p=0 "候选.mp4"
```

时长对上了再抽一帧看：`ffmpeg -y -ss 8 -i 候选.mp4 -vframes 1 -vf "crop=1920:250:0:830" p.png`，
若画面里已有金色英文 + 白色中文，就是成片。**更硬的证据**：该行文字与你的
`subs_data.py` 条目逐字相同且落在同一条时间窗内。

确认是成片后：**不要重烧**，改为做一次「归档件认证核验」并交付核验结果——
对 `subs_data.py` 里每一条取中点抽帧，分别统计 EN 行区 / CN 行区的亮像素数（应 >3000）
与「CN 行以下」的残留（`max` 应只来自自家文字），再核对零空档与末条到片尾的衔接。
可直接改路径复用 `audit_archive.py`（本工作流各片工作区下均有一份）。

### 20. 原片自带片尾卡时：保留，但在交付说明里提示可裁剪
有些片源最后 5~10s 是原频道的 logo 尾卡（实测占了 179.8~189.3s，约 9.5s）。
它不属于要翻译的内容，但**不要擅自剪掉**——先保留、拼上用户自己的「关注我」片尾，然后明确告诉用户
「原片末尾有 X 秒频道尾卡，要的话我可以裁掉」，由用户决定。

### 21. ⚠️ 原片烧屏硬字幕不一定等于音频口播——先验证再当权威文本

Step 0 说「硬字幕是最权威的文本来源」，**这条有前提**：硬字幕和音频得是同一套话。
2026-10-01 实测一支片子（穿短袖）二者完全是两套内容：

| | 内容 | 出处 |
|---|---|---|
| **音频**（观众听得见的） | 第三人称教学口播：`take the shirt and lie it face down on their bed. Then, tell them to bunch up the back of the shirt to the neck hole.` | 口播音轨 |
| **烧屏硬字幕** | 演示者第一人称台词：`So first we have to put the shirt on.` / `I'm going to start with my head, and I'm going to put it right here.` | 画面底部黑底白字（y≈1000-1080） |

两者语义平行（都在讲穿T恤）但**用词完全不同**，时间轴也对不上：
音频分段边界 9.21 / 15.59 / 24.65 / 35.01 / 41.89 vs 硬字幕换行 5.5 / 12.5 / 19.5 / 26.5 / 33.5 / 41.5。

**判定方法（别只跑一次 Whisper 就下结论）：**

1. **VAD 看有没有语音**：`transcribe(..., vad_filter=True)` 若语音覆盖 ~97% 时长（43.16/44.30s）且
   语种概率 1.0，说明音频是真口播，不是纯音乐 → Whisper 大概率没错。
2. **initial_prompt 对数概率对比**（Pitfall 18 的方法）——这是最决定性的一招：
   把**硬字幕原文**塞进 `initial_prompt`。Whisper 对 prompt 的偏向极强，
   若音频真说的是那句，输出会直接照抄；实测它**依然输出音频版措辞**（只吸收了开头几个词），
   就说明音频里根本不是那句话。
3. **局部窗口复验**：切 3 个窗口（如 0-5.5s / 27-33.5s / 42-44.3s）各跑一次，两套 prompt 都试。
   实测 42-44.3s 硬字幕是 `the design is on the right side`，音频稳定是 `the picture is on the front`。

**结论与做法：**
- 字幕必须跟**听得见的声音**走（否则观众看到的中英文字和耳朵听到的对不上）→ 采用音频版。
- 硬字幕属于「补充信息」，但和 Pitfall 13 的关键词卡不同：它整条都在遮罩区内，
  用 `black@1.0` 会把它一并盖掉。**交付时必须单独说明**：附一张「音频 vs 硬字幕」对照表，
  并主动提供两个改版选项——(a) 把双语块上移、让原字幕露出来（两块英文会并存，需用户确认）；
  (b) 反过来翻译硬字幕那套台词（更适合孩子直接学，但与音频不对应）。
- 不要让这种片子静默走完流程：**这是内容级分叉，交付说明里必须显式提示。**

---

### 22. 硬字幕「上沿」比默认遮罩顶还高时，必须反推 BOX_PAD_Y，不能套默认值

默认布局：`BOX_PAD_Y = 24` → 遮罩顶 `BOX_Y = 886`（1080p 大档）。
这个默认值**只在原片硬字幕上沿 ≥ 886 时才安全**。实测出现过上沿到 **y=877** 的片子
（`穿裤子.mp4`），套默认值会在遮罩上缘漏出约 9px 的原字幕上半截。

正确做法——**先测上沿，再定遮罩顶**：

```bash
# 1) 抽比默认遮罩更高的一条带（这里是 y820 起、260 高），1fps
ffmpeg -y -i SRC.mp4 -vf "fps=1,crop=1920:260:0:820" band3/%03d.png
```
```python
# 2) 找「亮像素 + 上下邻域有暗像素」= 描边白字（纯亮底色不算），统计每帧命中 y 区间
g = np.asarray(Image.open(p).convert('L')).astype(np.int16)
bright, dark = g > 200, g < 90
nb = np.zeros_like(bright)
for k in (1, 2, 3):
    nb[:-k] |= dark[k:]; nb[k:] |= dark[:-k]
cnt = (bright & nb).sum(axis=1)      # 每行的「描边白字」像素数
hit = np.where(cnt >= 25)[0]         # 阈值按字数调，25 约等于一行小字
```
取**所有帧里最高的那个上沿** `y_top`，然后：

```
BOX_PAD_Y = (EN_BOTTOM - EN_FONTSIZE) - (y_top - 10)     # 留 10px 余量
```

本片：`y_top = 877` → `BOX_PAD_Y = 44` → `BOX_Y = 866`，遮罩高 214px（19.8%）。

校验时不能只看「CN 行以下」——**必须单独看遮罩顶带（BOX_Y ~ BOX_Y+40）**，
残留应为 0。默认 verify 脚本只查底部会漏掉这个缺口。

> 顺带：因为遮罩变高，自检里的「占屏比例」会超出默认的 18%，这是**预期内的**，
> 不要为了压回 18% 去砍字号——那样反而让顶部再漏出来。

---


### 23. 固定单行布局 + 词级拼接的连字符瑕疵

**布局**：一旦采用 Step 2.5（一屏一句），每条字幕就固定一行 EN + 一行 CN，
`en_y=910` / `cn_y=988` / `box_y=886` / `box_h=VH-box_y`。不要为长句叠多行
drawtext、也不要动态改遮罩高度；长句应在 Step 2.5 阶段就拆成多条字幕。

**文本瑕疵**：`word_timestamps=True` 会把连字符词拆成多个 word，
`" ".join(words)` 拼回去会得到 `hip -hop`（Whisper 把 `hip-hop` 拆成
`hip` + `-hop`），SRT 与烧录画面都会带这个肉眼可见的错字。用
`norm_words()` 做精确串替换修掉（见 Step 2.5），并在交付前扫描全部
`en_*.txt`：命中 `' -'` 或连续空格就报错。逐句复核是硬要求，别只抽几帧看宽度。

### 24. 别把「学习文案选句」当成「硬字幕」

`video-english-xhs` 挑 8–10 句做小红书 / 飞书笔记是**正确**的；
硬字幕只烧这 8–10 句是 **bug**。先按 Step 0.5 建完整 manifest，再让下游
文案从这份完整清单里挑亮点。两者数据源相同、粒度不同，不要混用。

---

## Verification Checklist

Before delivering the final video:

- [ ] **开工前**已确认输入不是「我们自己烧过字的成片」：候选为 H.264 且时长 ≈ 原片 + 1.416s → 见 Pitfall 19
- [ ] **原片有烧屏硬字幕时**，已验证它与音频是同一套话（见 Pitfall 21）；内容级分叉已在交付说明里显式提示
- [ ] **有硬字幕时**已实测其「上沿 y」，并按它反推 `BOX_PAD_Y`（不能套默认 24，见 Pitfall 22）
- [ ] 校验图除「CN 行以下」外，**还单独查了遮罩顶带（BOX_Y~BOX_Y+40）**残留为 0
- [ ] **逐条通读生成的 `en_*.txt`**：无 `hip -hop` 类拼接瑕疵、无重复空格（Step 2.5 / Pitfall 23）
- [ ] **每屏只有 1 行英文 + 1 行中文**，无折行；长句已拆成多条独立字幕（Step 2.5）
- [ ] **无 1–2 词孤儿屏**：所有行 ≥3 词，且 `en_w(line) <= 1800px`；整句能放下的没被误拆
- [ ] `subtitle_manifest` 覆盖每一句可听见的台词；`subtitle_coverage_audit.md` 的 `missing` = 0
- [ ] 用户给的修正已进 `SUBS`，或显式标 `needs_review` 并在交付说明中点名
- [ ] Extract frames at 5+ timestamps spread across video duration
- [ ] Check each frame: text fully visible, no clipping
- [ ] Check mask: flush with video bottom, no gap
- [ ] Check apostrophes: `Let's` renders as straight `'`, not curly `'`
- [ ] Check timing: play video and listen — subtitles appear when speech starts
- [ ] Check gaps: no blank moments between subtitle entries
- [ ] Check file size: reasonable for the video length
- [ ] Check no subtitle appears before its audio is spoken
- [ ] **交付包里没有与 mp4 同目录同名的 .srt**（否则播放器会自动叠加成双重字幕，见 Pitfall 16）
- [ ] 抽帧扫描确认：最后一行字幕以下（`VH - SAFE_BOTTOM` 到 `VH`）为纯黑，无残留文本
- [ ] **片尾「关注我」已拼到末尾**（默认必做，见顶部 Preset Outro Video；除非用户明确说不要）
- [ ] **片尾衔接正常**：无跳帧 / 音画错位（编码格式不一致时必须先重编码 preset，见 Pitfall 17）
- [ ] **最终时长 ≈ 正片 + 片尾**（用 ffprobe 核对 duration，差值 <0.5s）

## Troubleshooting

**"Unable to find a suitable output format"**
→ Check filter.txt syntax. Common issue: unescaped `:` in paths.

**Subtitles appear too early/late**
→ Re-run whisper with `word_timestamps=True`. Compare word start/end with subtitle timing.

**Apostrophes show as curly quotes or spaces**
→ Switch from `text=` to `textfile=` parameter.

**Mask has a gap at the bottom**
→ Set `box_h = VH - box_y` instead of calculating from text height.

**Output file too large**
→ Use CRF 23 instead of high bitrate. Or use `-preset slow` for better compression.

**Chinese characters show as boxes**
→ Font doesn't support CJK. Use msyh.ttc (Windows), STHeiti (macOS), or wqy-microhei (Linux).

**Glitch/stutter at transition to preset outro**
→ Format mismatch. Re-encode preset to match or use filter-based concat instead of stream copy.
