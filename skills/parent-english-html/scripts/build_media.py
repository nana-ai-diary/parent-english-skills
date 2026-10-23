# -*- coding: utf-8 -*-
"""通用媒体构建：lesson.json 里写 cuts（分段起止秒），这里生成
   audio/full.mp3 + audio/segNN.mp3 + audio/segNN_slow.mp3
   img/poster.jpg + video/<videofile>

用法: python tools/build_media.py tools/lessons/03-baby-bath.json
"""
import io, json, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
SERIES = json.load(io.open(os.path.join(BASE, "series.json"), encoding="utf-8"))
# 素材目录优先级：环境变量 > lesson JSON 的 src_dir > series.json
VDIR = os.environ.get("PE_VIDEO_DIR") or SERIES["video_dir"]


def run(args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        print("FAIL", " ".join(args[:8]))
        print("   ", p.stderr.decode("utf-8", "ignore")[-400:])
        return False
    return True


def main(path):
    d = json.load(io.open(path, encoding="utf-8"))
    n = d.get("n") or "00"
    slug = d["slug"]
    vdir = d.get("src_dir") or VDIR
    src = os.path.join(vdir, d["src_video"])
    if not os.path.isfile(src):
        print("MISSING", src); sys.exit(1)
    dst = os.path.join(ROOT, "outputs", "亲子英语", slug)
    aud, img, vid = (os.path.join(dst, x) for x in ("audio", "img", "video"))
    for x in (aud, img, vid):
        os.makedirs(x, exist_ok=True)

    cuts = d["cuts"]
    poster_t = d.get("poster_t", min(cuts[0][1], 8) if cuts else 5)
    vname = d.get("video_file", slug + ".mp4")

    print("full audio …", flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "44100",
         "-c:a", "libmp3lame", "-b:a", "96k", os.path.join(aud, "full.mp3")])

    for i, (a, b) in enumerate(cuts, 1):
        nm = "seg%02d" % i
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % a, "-to", "%.2f" % b, "-i", src,
             "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k",
             os.path.join(aud, nm + ".mp3")])
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % a, "-to", "%.2f" % b, "-i", src,
             "-vn", "-af", "atempo=0.8", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
             "-b:a", "64k", os.path.join(aud, nm + "_slow.mp3")])

    run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % poster_t, "-i", src, "-frames:v", "1",
         "-vf", "scale=1280:-2", "-q:v", "4", os.path.join(img, "poster.jpg")])

    vout = os.path.join(vid, vname)
    print("720p encode …", flush=True)
    run(["ffmpeg", "-v", "error", "-y", "-i", src,
         "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "medium", "-crf", "30",
         "-profile:v", "main", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-c:a", "aac", "-b:a", "96k", "-ac", "1", vout])

    tot = sum(os.path.getsize(os.path.join(aud, f)) for f in os.listdir(aud))
    print("audio total %.2f MB / %d files" % (tot / 1048576, len(os.listdir(aud))))
    for f in ("img/poster.jpg", "video/" + vname):
        p = os.path.join(dst, f)
        print("%-34s %9d" % (f, os.path.getsize(p)) if os.path.isfile(p) else "%-34s MISSING" % f)


if __name__ == "__main__":
    p = sys.argv[1]
    if not os.path.isabs(p):
        p = os.path.join(ROOT, p)
    main(p)
