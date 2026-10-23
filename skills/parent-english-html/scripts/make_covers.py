# -*- coding: utf-8 -*-
"""亲子英语 · 批量封面裁剪
从竖版海报中裁掉「宝妈必看｜油管亲子口语」粉色条及其下方内容，只保留上方画面，
统一成 3:2 横版封面，输出到 outputs/亲子英语/covers/<n>.jpg
用法: python tools/make_covers.py [--verify]
"""
import io, json, os, subprocess, sys
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
MAN = json.load(io.open(os.path.join(BASE, "series.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "outputs", "亲子英语", "covers")
TARGET = 3 / 2.0          # 横版比例
COVER_W = 960             # 输出宽度

# 全部 34 张海报的「宝妈必看」粉条落在 0.469–0.545（实测），逐张检测后在上沿上方 1% 处下刀。
# 注意粉条有深浅两档：深的 (230,120,180) 和浅的 (255,200,200)，
# 旧判据「b-g>8」会把浅粉排除掉 → 整张漏检。新判据只看 r 明显大于 g/b。
FALLBACK_FRAC = 0.468

# 没有配图海报的课 → 从视频取帧做封面。(取帧时刻秒, 字幕条上沿比例 or None=旧逻辑)
# 挑帧要求：主体清楚、构图能裁成 3:2、且字幕条裁掉后不残缺。
VIDEO_FRAME = {
    "23": (6.0, None),        # 游乐设施名字（沿用最早的整幅取帧）
    "35": (103.0, 0.850),     # 折纸飞机：户外举起成品的镜头
}


def detect_band_top(path):
    """返回「宝妈必看」粉色条的顶部 y 比例；检测不到返回 None"""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    step = max(1, W // 260)
    gapmax = int(W * 0.02 / step) + 1

    def pk(c):
        r, g, b = c[:3]
        return r > 235 and r - g > 28 and r - b > 18

    for y in range(int(H * 0.30), int(H * 0.70)):
        run = mx = gap = 0
        for x in range(0, W, step):
            if pk(px[x, y]):
                run += 1
                gap = 0
            else:
                gap += 1
                if gap > gapmax:
                    run = 0
            mx = max(mx, run)
        if mx / (W / step) > 0.55:
            return y / H
    return None


def crop_cover(src, dst, frac):
    """裁到 3:2 横版：高度锁在 frac（粉条上沿），多余的部分从两侧或底部切掉。"""
    im = Image.open(src).convert("RGB")
    W, H = im.size
    ch = int(H * frac)
    cw = int(ch * TARGET)
    if cw > W:                              # 画面偏高 → 用满宽，往下多留一点（仍在粉条之上）
        cw = W
        ch = int(W / TARGET)
    x0 = (W - cw) // 2                      # 居中裁
    im = im.crop((x0, 0, x0 + cw, ch))
    h = int(COVER_W * im.size[1] / im.size[0])
    im = im.resize((COVER_W, h), Image.LANCZOS)
    im.save(dst, quality=86, optimize=True)
    return im.size


def frame_cover(video, dst, t=6.0, capfrac=None):
    """没有海报的课 → 从视频里取一帧做封面。

    capfrac=None（老课 23）沿用旧逻辑：缩到 1600 宽后整体取 3:2。
    capfrac=0.xx（新做法）先把「烧录字幕条」整条裁掉再取 3:2——
    1 帧 1 秒地 OCR 出来的字幕条在 1080p 上落在 y≈0.87 以下，取它上沿即可，
    否则封面底下会压着一行中英字幕，很难看。
    """
    tmp = dst + ".raw.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video,
                    "-frames:v", "1", "-q:v", "3", tmp], check=True)
    im = Image.open(tmp).convert("RGB")
    W, H = im.size
    if capfrac is None:
        im = im.resize((1600, int(1600 * H / W)), Image.LANCZOS)
        W, H = im.size
        ch = int(W / TARGET)
        y0 = max(0, int(H * 0.10))
        if y0 + ch > H:
            y0 = H - ch
        out = im.crop((0, y0, W, y0 + ch))
    else:
        ch = int(H * capfrac)
        cw = int(ch * TARGET)
        if cw > W:                          # 画面不够宽 → 用满宽，从顶部算高
            cw, ch = W, int(W / TARGET)
        x0 = (W - cw) // 2
        out = im.crop((x0, 0, x0 + cw, ch))
    out = out.resize((COVER_W, int(COVER_W / TARGET)), Image.LANCZOS)
    out.save(dst, quality=86, optimize=True)
    os.remove(tmp)
    return out.size


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    os.makedirs(OUT, exist_ok=True)
    idir = MAN["image_dir"]
    vdir = MAN["video_dir"]
    made, verify = [], []
    for L in MAN["lessons"]:
        if only and L["n"] != only:
            continue
        dst = os.path.join(OUT, "%s.jpg" % L["n"])
        if L.get("image"):
            src = os.path.join(idir, L["image"])
            det = detect_band_top(src)
            if det:
                frac = max(det - 0.008, 0.35)   # 上沿再抬 0.8%，留一点余量
                tag = "det@%.3f" % det
            else:
                frac = FALLBACK_FRAC
                tag = "fallback@%.3f" % FALLBACK_FRAC
            size = crop_cover(src, dst, frac)
        else:
            t, cap = VIDEO_FRAME.get(L["n"], (6.0, None))
            size = frame_cover(os.path.join(vdir, L["video"]), dst, t, cap)
            frac, tag = t, "video-frame@%ss" % t
        made.append((L["n"], L["zh"], frac, tag, size))
        verify.append((L["n"], L["zh"], Image.open(dst).convert("RGB").resize((320, 213))))
        print("%s %-14s frac=%.3f %-11s %s %6d B" % (
            L["n"], L["zh"], frac, tag, size, os.path.getsize(dst)))

    # 拼版便于人工核对
    cols = 5
    rows = (len(verify) + cols - 1) // cols
    sh = Image.new("RGB", (cols * 328 + 8, rows * 246 + 8), "white")
    d = ImageDraw.Draw(sh)
    os.makedirs(os.path.join(ROOT, "work_cover"), exist_ok=True)
    for i, (n, zh, im) in enumerate(verify):
        c, r = i % cols, i // cols
        sh.paste(im, (8 + c * 328, 8 + r * 246))
        d.text((10 + c * 328, 8 + r * 246 + 218), n + " " + zh, fill=(0, 0, 0))
    sh.save(os.path.join(ROOT, "work_cover", "cover_check.jpg"), quality=82)
    print("\n共 %d 张封面 → %s" % (len(made), OUT))


if __name__ == "__main__":
    main()
