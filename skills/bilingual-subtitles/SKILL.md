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

## Preset Outro Video（可选 / OPTIONAL）

> 安装时加固说明：原 skill 将片尾视频标记为 **ALWAYS / MANDATORY**，
> 并硬编码了作者本机的片尾视频绝对路径（形如 `.../Videos/亲子视频-定稿/预设.mp4`）。
> 现改为**默认不拼接**：只有当用户明确提供片尾视频路径时才执行 Step 7。

**默认行为：不拼接片尾。** 仅当用户显式给出 outro 视频路径（例如 `--outro D:\xxx.mp4`）
或在 `config.example.yaml` 中配置了非空的 `preset_video` 时，
才在字幕烧制完成后用 ffmpeg concat demuxer 追加（见 Step 7）。

拼接前必须先确认该路径存在且用户确认过内容，否则直接跳过这一步并告知用户。

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
EN_FONTSIZE = 42
CN_FONTSIZE = 42
LINE_GAP = 10
SAFE_BOTTOM = 20        # CN text bottom edge distance from video bottom
BOX_PAD_Y = 16           # vertical padding inside mask
BOX_OPACITY = 0.86       # black mask opacity

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

### Step 7: Append Outro Video（仅在用户指定时执行 / only if user provided）

**默认跳过本步骤。** 仅当用户提供了片尾视频路径时才执行；未提供则直接交付字幕版成片。

```python
# 由用户指定，不要使用任何硬编码路径
PRESET_VIDEO = None  # e.g. r"D:\my\outro.mp4"
```

执行前先检查 `PRESET_VIDEO` 是否为 None 或文件是否存在，任一不满足就跳过并告知用户。

Use ffmpeg concat demuxer:

```python
import subprocess, os, tempfile

# 1. Re-encode preset to match subtitled video specs (if needed)
# Both videos must have same codec, resolution, fps, and audio format
# Probe the subtitled video first:
#   ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate -of json subtitled.mp4

# 2. Create concat list file
concat_list = os.path.join(tempfile.gettempdir(), "concat_list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    f.write(f"file '{os.path.abspath(subtitled_mp4)}'\n")
    f.write(f"file '{os.path.abspath(preset_mp4)}'\n")

# 3. Concatenate
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c", "copy",          # stream copy if formats match
    "-movflags", "+faststart",
    output_final_mp4
], check=True)
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

| Resolution | Font Size | LINE_GAP |
|------------|-----------|----------|
| 1280×720 | 32px | 8px |
| 1920×1080 | 42px | 10px |
| 1920×1080（用户要求「字大一点」） | EN 62 / CN 60 | 16px |
| 3840×2160 | 84px | 20px |

「字大一点 + 遮罩大一点」的推荐组合（1080p）：`EN_FONTSIZE=62, CN_FONTSIZE=60, LINE_GAP=16, SAFE_BOTTOM=32, BOX_PAD_Y=24` → 遮罩高约 194px（占画面 18%），能完整盖住原片底部的歌词条（y≈968-1066）。
宽度自检：`ImageFont.getlength(text)` 最大值应 < `VW - 120`。

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

### 14. 长句拆分按「乐句/词级时间戳」切，不按字符数硬切
用户要求拆分长句时：先用 `ImageFont.getlength()` 量出实际像素宽度确认是否真的超框（1920 宽留 120px 边距 ≈ 可放 34 个 62px 拉丁字符），再用 Whisper 的词级时间戳找到自然停顿点。备注：字幕条上的英文句子即便 40 字符也可能完全放得下，不要为了「看起来长」而拆。

### 15. 不确定的短促过门句：宁可用 gap-fill 延续上一句
歌里常有 0.5~1s 的口白/气口（两个模型给出完全不同的内容）。**不要凭猜测新增一行字幕**，直接按 gap-fill 让上一句延续到下一句开始即可；同时要在交付说明里点出这个位置。

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
- [ ] （仅当指定了片尾视频时）片尾已追加到末尾
- [ ] （仅当指定了片尾视频时）正片与片尾衔接流畅、无跳帧

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
