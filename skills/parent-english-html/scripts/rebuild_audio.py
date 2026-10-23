# -*- coding: utf-8 -*-
"""只重切分段音频（segNN.mp3 / segNN_slow.mp3），不碰 full.mp3 / 封面 / 视频。

改 cuts 只影响分段音频 —— `video/*.mp4` 是整条片子压的、`poster` 只取决于
`poster_t`，两者与 cuts 无关。所以「切点精修」这种改动只需重切音频，
不用把 470 MB 视频重编码一遍。

用法:
  python tools/rebuild_audio.py                 # 全系列
  python tools/rebuild_audio.py 05 08 29        # 只做某几课
  python tools/rebuild_audio.py --check         # 只报告会删掉哪些多余的 seg 文件
"""
import io, json, os, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
OUT = os.path.join(ROOT, "outputs", "亲子英语")
SERIES = json.load(io.open(os.path.join(BASE, "series.json"), encoding="utf-8"))
VDIR = os.environ.get("PE_VIDEO_DIR") or SERIES["video_dir"]


def run(args):
    p = subprocess.run(args, capture_output=True)
    if p.returncode != 0:
        print("   FAIL", " ".join(args[:6]))
        print("   ", p.stderr.decode("utf-8", "ignore")[-300:])
        return False
    return True


def main():
    argv = sys.argv[1:]
    check = "--check" in argv
    picks = {a for a in argv if not a.startswith("--")}
    total = 0
    for f in sorted(os.listdir(os.path.join(BASE, "lessons"))):
        if not f.endswith(".json"):
            continue
        if picks and f[:2] not in picks:
            continue
        d = json.load(io.open(os.path.join(BASE, "lessons", f), encoding="utf-8"))
        slug = d["slug"]
        n = d.get("n") or f[:2]
        src = os.path.join(VDIR, d["src_video"])
        aud = os.path.join(OUT, slug, "audio")
        if not os.path.isdir(aud):
            print("跳过 %-28s 无 audio 目录" % slug)
            continue
        if not os.path.isfile(src):
            print("跳过 %-28s 缺源视频 %s" % (slug, src))
            continue
        cuts = d["cuts"]
        want = set()
        for i, (a, b) in enumerate(cuts, 1):
            nm = "seg%02d" % i
            want.add(nm + ".mp3")
            want.add(nm + "_slow.mp3")
            if check:
                continue
            run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % a, "-to", "%.2f" % b, "-i", src,
                 "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "64k",
                 os.path.join(aud, nm + ".mp3")])
            run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % a, "-to", "%.2f" % b, "-i", src,
                 "-vn", "-af", "atempo=0.8", "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame",
                 "-b:a", "64k", os.path.join(aud, nm + "_slow.mp3")])
        # 段落变少时把多余的 seg 文件清掉（否则页面/校验会看到孤儿文件）
        stale = [x for x in os.listdir(aud)
                 if (x.startswith("seg") and x.endswith(".mp3")) and x not in want]
        if check:
            print("%-28s cuts=%d  多余文件 %s" % (slug, len(cuts), stale or "无"))
            continue
        for x in stale:
            os.remove(os.path.join(aud, x))
        total += len(cuts)
        print("%-28s 重切 %d 段%s" % (slug, len(cuts), "，清理 %d 个多余文件" % len(stale) if stale else ""))
    print("\n共重切 %d 段音频" % total)


if __name__ == "__main__":
    main()
