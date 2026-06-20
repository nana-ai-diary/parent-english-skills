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

## Preset Outro Video

**ALWAYS append this video to the end of the final output:**

```
C:\Users\32730\Videos\亲子视频-定稿\预设.mp4
```

After subtitle burning is complete, concatenate the preset video using ffmpeg concat demuxer (see Step 7 below).

---

## Why NOT moviepy

**moviepy's TextClip has a fatal flaw**: it generates text images with **0px bottom padding**. Text content extends to the very last pixel row, causing descenders (g, y, p) and CJK bottom strokes to appear clipped when composited. No amount of LINE_SPACING or MARGIN tweaking reliably fixes this without visible artifacts.

**ffmpeg drawtext renders directly on video frames** — no intermediate image generation, no clipping, no workarounds needed. Combined with `drawbox` for the background mask, this produces clean, professional results.

---

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

### Step 7: Append Preset Outro Video

**MANDATORY**: After subtitle burning, concatenate the preset outro video to the end of the subtitled video.

```python
PRESET_VIDEO = r"C:\Users\32730\Videos\亲子视频-定稿\预设.mp4"
```

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
| macOS | `/System/Library/Fonts/STHeiti Medium.ttc` | STHeiti |
| Linux | `/usr/share/fonts/truetype/wqy/wqy-microhei.ttc` | WenQuanYi |

### Font Size by Resolution

| Resolution | Font Size | LINE_GAP |
|------------|-----------|----------|
| 1280×720 | 32px | 8px |
| 1920×1080 | 42px | 10px |
| 3840×2160 | 84px | 20px |

### Safe Area (Mobile Compliance)

- **SAFE_BOTTOM**: Distance from video bottom to CN text bottom edge
  - 20px: mask flush, suitable for most platforms
  - 40-60px: extra margin for platforms with UI overlays
- **Mask bottom**: Always set `box_h = VH - box_y` to ensure flush with video bottom

### Colors

- English: `0xFFD700` (gold/yellow)
- Chinese: `white`
- Border: `black`, width 2px
- Mask: `black@0.86` (86% opacity)

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
- [ ] Check preset outro video is appended at the end
- [ ] Check transition between main video and preset outro is smooth

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
