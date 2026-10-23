# -*- coding: utf-8 -*-
"""单课预处理：抽 16k 音频 → small 模型转写 → 生成字幕拼图。

用法: python tools/prep.py 03
产出（均在 work_prep/NN/）：
  audio.wav        16k 单声道音频（转写用）
  transcript.txt   带时间戳的逐句转写，便于人读校对
  transcript.json  [{start,end,text}]
  sheet.jpg        视频烧录字幕条拼图（每 1 秒一帧，按 3x24 铺）
  info.txt         ffprobe 出来的视频信息（时长/分辨率/码率）
"""
import io, json, os, subprocess, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
sys.path.insert(0, BASE)
SERIES = json.load(io.open(os.path.join(BASE, "series.json"), encoding="utf-8"))
VDIR = os.environ.get("PE_VIDEO_DIR") or SERIES["video_dir"]
PREP = os.path.join(ROOT, "work_prep")
FONT = "C\\:/Windows/Fonts/arialbd.ttf"


def run(args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        print("FAIL", " ".join(args[:8]))
        print("   ", p.stderr.decode("utf-8", "ignore")[-500:])
        return False
    return True


def probe(path):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate",
                        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
                        "-of", "default=noprint_wrappers=1", path], capture_output=True)
    return p.stdout.decode("utf-8", "ignore").strip()


def transcribe(wav, json_out, txt_out, model="small"):
    from faster_whisper import WhisperModel
    t0 = time.time()
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=4)
    segs, info = m.transcribe(wav, beam_size=1, temperature=0, vad_filter=True,
                              condition_on_previous_text=False,
                              no_speech_threshold=0.6, log_prob_threshold=-1.0)
    rows = []
    for s in segs:
        rows.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
    io.open(json_out, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False, indent=1))
    with io.open(txt_out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write("[%6.2f → %6.2f] %s\n" % (r["start"], r["end"], r["text"]))
    print("transcribe(%s) %.1fs, %d segments" % (model, time.time() - t0, len(rows)), flush=True)
    for r in rows:
        print("  [%6.2f] %s" % (r["start"], r["text"]), flush=True)


def main():
    n = sys.argv[1] if len(sys.argv) > 1 else "03"
    L = next((x for x in SERIES["lessons"] if x["n"] == n), None)
    if not L:
        print("no lesson", n); sys.exit(1)
    src = os.path.join(VDIR, L["video"])
    if not os.path.isfile(src):
        print("MISSING", src); sys.exit(1)
    d = os.path.join(PREP, n)
    os.makedirs(d, exist_ok=True)
    wav = os.path.join(d, "audio.wav")
    print("==", n, L["zh"], L["en"], "==")
    print(probe(src))

    if not os.path.isfile(wav):
        run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
             "-c:a", "pcm_s16le", wav])
    print("wav", os.path.getsize(wav))

    js, tx = os.path.join(d, "transcript.json"), os.path.join(d, "transcript.txt")
    if not os.path.isfile(js):
        transcribe(wav, js, tx, "small")
    else:
        print("transcript exists, skip")

    # 字幕条拼图（注意：fontfile / text 的值必须用单引号包住，否则 ffmpeg 在
    # 无 shell 的情况下会把 C\: 和 %{pts\:hms} 里的转义冒号解析错，tile 报 parse error）
    sheet = os.path.join(d, "sheet.jpg")
    if not os.path.isfile(sheet):
        run(["ffmpeg", "-v", "error", "-y", "-i", src,
             "-vf", ("fps=1,crop=iw:ih*0.11:0:ih*0.705,scale=560:-2,"
                     "drawtext=fontfile='%s':text='%%{pts\\:hms}':x=4:y=2:fontsize=18:"
                     "fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=3,"
                     "tile=3x24:padding=4:color=gray" % FONT),
             "-frames:v", "1", sheet])
    # 底部 30% 拼图（抓 Tip 卡片）
    tb = os.path.join(d, "tipstrip.jpg")
    if not os.path.isfile(tb):
        run(["ffmpeg", "-v", "error", "-y", "-i", src,
             "-vf", ("fps=1/2,crop=iw:ih*0.32:0:ih*0.66,scale=620:-2,"
                     "drawtext=fontfile='%s':text='%%{pts\\:hms}':x=4:y=2:fontsize=18:"
                     "fontcolor=yellow:box=1:boxcolor=black@0.7:boxborderw=3,"
                     "tile=3x20:padding=4:color=gray" % FONT),
             "-frames:v", "1", tb])
    for f in ("sheet.jpg", "tipstrip.jpg"):
        p = os.path.join(d, f)
        print("%-14s %8d" % (f, os.path.getsize(p)) if os.path.isfile(p) else "%-14s MISSING" % f)
    print("dir:", d)


if __name__ == "__main__":
    main()
