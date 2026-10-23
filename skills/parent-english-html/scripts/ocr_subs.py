# -*- coding: utf-8 -*-
"""烧录字幕 OCR 流水线（ffmpeg 管道读帧，不落盘）

用法:
  python tools/ocr_subs.py 20                          # 单课（编号见 tools/series.json）
  python tools/ocr_subs.py --all                       # 全系列
  python tools/ocr_subs.py --all 01 05 20              # 指定几课

输出: work_ocr/<编号>.jsonl   每行 {"t":秒, "txt":"..."}（字幕变化时才产生新行）
      work_ocr/<编号>.txt     人读友好

注：帧不写磁盘。沙箱对 shutil.rmtree/批量删除有守卫，脚本一旦删目录会被直接杀掉。
"""
import io, json, os, re, subprocess, sys, time

import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
import rapidocr_onnxruntime.utils as _U

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "work_ocr")

FPS = 1
WIDTH = 1100
# 裁画面下方 30%：实测全系列英文烧录字幕固定在 y 0.83-0.91、中文 0.87-0.99。
# 不能再裁窄——条太扁（<150px 高）检测器会直接空手而归；也不能裁太高，
# 否则会把画面里的 Tip 卡片（y 0.76-0.79）读进来，靠下面的 CY_MIN 再滤一道。
CROP = "crop=iw:ih*0.30:0:ih*0.70"
CY_MIN = 0.33           # 只保留纵向中心在下 2/3 的文本框（字幕）；提示卡会被滤掉

# 关键提速：默认 limit_type=min 会把 1100×220 的字幕条**放大**到 3600+ 宽再做检测
# （2.5s/帧）。改成 max + 关掉角度分类后降到 ~1.4s/帧。
DET_MODEL = os.path.join(str(_U.root_dir), "models", "ch_PP-OCRv3_det_infer.onnx")

SOI, EOI = b"\xff\xd8", b"\xff\xd9"


def new_ocr():
    return RapidOCR(det_limit_side_len=960, det_limit_type="max",
                    det_model_path=DET_MODEL, use_angle_cls=False)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def frames(src, fps=FPS, crop=CROP, width=WIDTH):
    """从 ffmpeg 的 mjpeg 管道里逐帧产出 (序号, PIL 图)，完全不落盘"""
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-i", src,
           "-vf", "fps=%d,%s,scale=%d:-2" % (fps, crop, width),
           "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         bufsize=10 ** 7)
    buf, idx = b"", 0
    while True:
        chunk = p.stdout.read(1 << 16)
        if not chunk:
            break
        buf += chunk
        while True:
            s = buf.find(SOI)
            e = buf.find(EOI, s + 2) if s >= 0 else -1
            if s < 0 or e < 0:
                break
            jpg, buf = buf[s:e + 2], buf[e + 2:]
            idx += 1
            yield idx, np.asarray(Image.open(io.BytesIO(jpg)).convert("RGB"))
    try:
        p.stdout.close()
    except Exception:
        pass
    p.wait()


def run_one(n, src, ocr, fps=FPS):
    rows, prev = [], "<INIT>"
    nf = 0
    t0 = time.time()
    for idx, im in frames(src, fps):
        nf = idx
        res, _ = ocr(im)
        H = im.shape[0]
        keep = []
        for box, txt, _sc in (res or []):
            ys = [p[1] for p in box]
            if ((min(ys) + max(ys)) / 2.0) / H >= CY_MIN:
                keep.append(txt)
        txt = " | ".join(keep).strip()
        if txt and norm(txt) == prev:
            continue
        prev = norm(txt)
        rows.append({"t": round((idx - 1) / float(fps), 2), "txt": txt})
    os.makedirs(OUT, exist_ok=True)
    with io.open(os.path.join(OUT, "%s.jsonl" % n), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with io.open(os.path.join(OUT, "%s.txt" % n), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write("%7.2f  %s\n" % (r["t"], r["txt"]))
    print("[ocr] %s frames=%d lines=%d %.1fs" % (n, nf, len(rows), time.time() - t0), flush=True)


def main():
    args = sys.argv[1:]
    series = json.load(io.open(os.path.join(ROOT, "tools", "series.json"), encoding="utf-8"))
    vdir = series["video_dir"]
    by_n = {l["n"]: l for l in series["lessons"]}
    if args and args[0] == "--all":
        picks = args[1:] or [l["n"] for l in series["lessons"]]
    else:
        picks = [args[0]]
    ocr = new_ocr()
    for n in picks:
        l = by_n[n]
        src = l["video"] if os.path.isabs(l["video"]) else os.path.join(vdir, l["video"])
        if not os.path.exists(src):
            print("[ocr] %s SKIP %s" % (n, src), flush=True)
            continue
        run_one(n, src, ocr)


if __name__ == "__main__":
    main()
