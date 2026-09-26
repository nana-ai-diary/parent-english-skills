---
name: bilingual-subtitles
description: 用ffmpeg drawtext+drawbox烧制中英双语字幕（带半透明遮罩背景），并拼接片尾预设视频。当需要给视频加双语字幕、字幕叠加、带背景的文字字幕时使用。包含whisper时间轴校准、安全区域规则和预设视频拼接。Burn bilingual (EN+CN) subtitles with semi-transparent background mask using ffmpeg drawtext+drawbox, then append preset outro video. Use when adding bilingual subtitles, subtitle overlays, or text captions with background to video.
version: 2.0.0
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

1. 读 skills 配置文件的 `preset_video` 字段（安装后位于 `~/.workbuddy/skills/parent-english.config.yaml`，
   模板见仓库根目录 `config.example.yaml`）。典型片尾规格：约 1.4s / 1920×1080 / 30fps。
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

音乐视频 / 儿歌视频常在底部有烧死的歌词条。**它是最权威的文本来源**，Whisper 听歌时会把歌词听错（例：`Moon cakes, moon cakes are round` 被听成 `Moon kicks, moon kicks around`），甚至在器乐段凭空编造整句歌词。先做这一步可以避免全部这类错误。

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
# 遮罩不透明度：原片底部已烧硬字幕 → 1.0 全不透明（见 Pitfall 13）；无硬字幕 → 0.86
BOX_OPACITY = 1.0       # (0.86)
# 上面这组参数 → 遮罩高约 194px（占画面 18%），可完整盖住 1080p 底部硬字幕条（y≈905-1060）

# Layout calculation
cn_y = VH - SAFE_BOTTOM - CN_FONTSIZE   # CN text top
en_y = cn_y - LINE_GAP - EN_FONTSIZE    # EN text top
box_y = en_y - BOX_PAD_Y
box_h = VH - box_y                       # MASK FLUSH WITH VIDEO BOTTOM

filter_parts = []
for i, (start, end, en, cn) in enumerate(SUBS):
    timing = f"between(t\\,{start}\\,{end})"

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
PRESET_VIDEO = read_config()["preset_video"]   # e.g. r"<你的片尾视频>.mp4"
```

**先把预设片尾重编码成与正片一致的规格，再 concat**（实测两个坑，都会产出「看起来成功但时长/音画不对」的坏文件）：

| 不一致项 | 症状（实测） | 要求 |
|----------|--------------|------|
| **音频采样率不同**（preset 48k vs 正片 44.1k） | 最终 duration 变成 **136.3s** 而不是 125.2s —— 正片音轨被按 48/44.1 拉伸了约 11s，音画错位 | preset 音频必须 resample 成正片的采样率 |
| 视频 codec 不同（preset HEVC vs 正片 H.264） | `-c copy` 侥幸能拼，但 MP4 里混合 codec，部分播放器/平台会花屏或拒绝播放 | preset 视频转成 H.264 |

先 probe 正片拿到目标采样率，再重编码 preset：

```bash
# 1) 取正片的音频采样率（本机实测是 44100，请以 ffprobe 结果为准）
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

**原片硬字幕的定位与复验（黄字关键词 / 歌词条通用）**：
- 定位：按 1fps 抽 `crop=1920:150:0:930` 的底带，逐帧统计黄色像素行范围（`r>190 & g>150 & b<130`），
  得到硬字幕的 y 区间（实测两支片子分别落在 905-940 / 956-1045）。**遮罩 `box_y` 必须在这条带的上沿之上**。
- 复验：渲染完成后抽帧统计「自己 EN 行以下」的黄色像素数，应当为 0。
  ⚠️ 我自己的 EN 字幕就是黄色 `0xFFD700`，所以统计区间要避开 EN 文字行（如 EN 占 y 908-976 时，只统计 y 976-1080），
  否则会把自家文字算成残留。
- 何时不要盖：若原片硬字幕是**关键词/单词卡**这类「补充信息」而非重复内容，盖掉会损失教学信息。
  此时应把双语字幕块整体上移（遮罩改成不贴底的中段条带），让原关键词露在下面——务必先问用户或交付时明确提示。

### 14. 长句拆分按「乐句/词级时间戳」切，不按字符数硬切
用户要求拆分长句时：先用 `ImageFont.getlength()` 量出实际像素宽度确认是否真的超框（1920 宽留 120px 边距 ≈ 可放 34 个 62px 拉丁字符），再用 Whisper 的词级时间戳找到自然停顿点。备注：字幕条上的英文句子即便 40 字符也可能完全放得下，不要为了「看起来长」而拆。

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
- 交付前 ffprobe 核对：最终 duration ≈ 正片 + 片尾（如 123.79 + 1.42 = 125.18s）。

---

## Verification Checklist

Before delivering the final video:

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
