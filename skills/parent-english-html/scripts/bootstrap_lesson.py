# -*- coding: utf-8 -*-
"""新一课脚手架：登记到 series.json + 生成 lesson JSON 骨架 + 用 OCR 行填初稿。

为什么需要它
------------
一个新视频要走完整条链路，前两步是「登记」和「给 part2 一个起点」：
`prep.py` 靠 series.json 找视频；`apply_p2.py` 的全局对齐 DP 需要 part2
先有**分段文本**（哪怕很粗）才能对上 OCR 字幕。本脚本把这两步做掉。

用法
----
① 登记 + 生成骨架：
   python tools/bootstrap_lesson.py add --no 35 --slug 35-feeding-cat \\
       --zh 喂猫 --en "Feeding the Cat" --video "37.喂猫.mp4" \\
       --cat 生活起居 --age 2-4 --diff ★★

② 跑完 prep.py 与 ocr_subs.py 之后，用 OCR 行把 part2 的 en 填成初稿
   （按行数 9 等分，同时把 cuts 设成对应时间窗）：
   python tools/bootstrap_lesson.py fill --no 35
"""
import io, json, os, re, subprocess, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
SER = os.path.join(BASE, "series.json")
LESSONS = os.path.join(BASE, "lessons")
SEG_N = 9                     # 约定：每课 9 段 / 3 天


def load(f):
    return json.load(io.open(f, encoding="utf-8"))


def save(f, obj):
    io.open(f, "w", encoding="utf-8").write(json.dumps(obj, ensure_ascii=False, indent=1))


def arg(name, default=None):
    a = sys.argv
    return a[a.index("--" + name) + 1] if ("--" + name) in a else default


def dur_of(src):
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", src], capture_output=True)
    try:
        return round(float(p.stdout.decode().strip()), 2)
    except Exception:                                   # noqa: BLE001
        return 60.0


# ---------------- add ----------------
def cmd_add():
    n = arg("no")
    slug = arg("slug")
    if not n or not slug:
        print("需要 --no 与 --slug"); sys.exit(1)
    s = load(SER)
    vdir = s.get("video_dir", "")
    video = arg("video")
    if not video:
        print("需要 --video（源目录里的文件名）"); sys.exit(1)
    src = os.path.join(vdir, video)
    by = arg("by", "")                       # YouTube 频道，如 @babylist
    entry = {"n": n, "src": arg("src", n), "by": by, "slug": slug,
             "zh": arg("zh", ""), "en": arg("en", ""),
             "video": video, "image": arg("image", ""),
             "cat": arg("cat", "生活起居"), "age": arg("age", "2–3 岁"),
             "diff": int(arg("diff", "2"))}
    s.setdefault("lessons", [])
    for i, L in enumerate(s["lessons"]):
        if L.get("n") == n:
            s["lessons"][i] = entry
            break
    else:
        s["lessons"].append(entry)
    s["lessons"].sort(key=lambda x: x["n"])
    save(SER, s)
    print("✓ series.json 已登记 %s %s" % (n, slug))

    lj = os.path.join(LESSONS, slug + ".json")
    if os.path.exists(lj):
        print("… lesson JSON 已存在，未覆盖：%s" % lj)
        return
    dur = dur_of(src) if os.path.isfile(src) else 60.0
    step = dur / SEG_N
    cuts = [[round(i * step, 2), round((i + 1) * step, 2)] for i in range(SEG_N)]
    ez = arg("zh", "")
    d = {
        "n": n, "slug": slug, "src_video": video,
        "video_file": slug.split("-", 1)[-1] + ".mp4",
        "zh": ez, "en": arg("en", ""),
        "brand_zh": "%s · %s" % (n, ez), "lesson_cn": "TODO 一句话学习要点",
        "title_tag": "%s · %s %s" % (n, ez, arg("en", "")),
        "key_check": "%s.check" % re.sub(r"[^a-z0-9]", "", slug.split("-", 1)[-1])[:6],
        "key_fav": "%s.fav" % re.sub(r"[^a-z0-9]", "", slug.split("-", 1)[-1])[:6],
        "source": ("来源：YouTube %s" % by) if by else "来源：YouTube 儿童亲子视频 · 自剪整理",
        "disclaim_src": ("英文原文与视频版权归原作者（YouTube %s）所有，此处仅作学习用途整理"
                         "（视频已自行剪辑并重配中英字幕）。" % by) if by else
                        "英文原文与视频版权归原作者所有，此处仅作学习用途整理（视频已自行剪辑并重配中英字幕）。",
        "disclaim_mid": "TODO 这一课的安全提醒（滑梯/车门/水温…）",
        "poster_t": round(min(dur * 0.2, 15), 2),
        "cuts": cuts,
        "tags": [{"t": arg("cat", "生活起居")}],
        "part1": {"dur": dur, "blurb": "TODO 30 字导语",
                  "video_title": "TODO 视频标题",
                  "full": "audio/full.mp3", "video": "video/" + slug.split("-", 1)[-1] + ".mp4",
                  "poster": "img/poster.jpg"},
        "part2": ([{"type": "day", "id": "d%d" % i, "t": "Day %d｜TODO" % i} for i in range(1, SEG_N + 1)]),
        "part3": [{"band": b, "title": "%s · TODO" % b, "rows": []} for b in ("A", "B", "C", "D")],
        "part4": [{"g": "A · TODO", "rows": []}],
        "part5": [{"kind": "选择", "q": "TODO", "opts": "A. …　　B. …　　C. …", "ans": "A"}],
        "part6": {"lead": "这些不算「错」，只是中文直译会听起来别扭。",
                  "rows": [["TODO 中式英语", "TODO 地道说法", "TODO 说明"]],
                  "card": {"h": "TODO", "rows": ["TODO"]}},
    }
    # part2 里穿插 9 个空白 seg（apply_p2 会按 OCR 重排，这里只占位）
    p2 = []
    for i in range(1, SEG_N + 1):
        p2.append({"type": "day", "id": "d%d" % (((i - 1) // 3) + 1),
                   "t": "Day %d｜TODO" % (((i - 1) // 3) + 1)})
        p2.append({"type": "seg", "no": "%02d" % i, "ti": "TODO",
                   "audio": "seg%02d.mp3" % i, "slow": "seg%02d_slow.mp3" % i,
                   "en": "", "cn": "TODO"})
    d["part2"] = p2
    save(lj, d)
    print("✓ 骨架已生成 %s（%d 段，时长 %.1fs）" % (lj, SEG_N, dur))
    print("\n下一步：\n  1) python tools/prep.py %s        # 转写 + 字幕拼图\n"
          "  2) python tools/ocr_subs.py %s     # OCR 烧录字幕\n"
          "  3) python tools/bootstrap_lesson.py fill --no %s\n"
          "  4) 读 sheet.jpg / tipstrip.jpg / transcript.txt，把 part3-part7 的中文内容写好\n"
          "  5) python tools/rebuild_all.py %s" % (n, n, n, n))


# ---------------- fill ----------------
def cmd_fill():
    n = arg("no")
    if not n:
        print("需要 --no"); sys.exit(1)
    s = load(SER)
    slug = next((L["slug"] for L in s["lessons"] if L.get("n") == n), None)
    if not slug:
        print("series.json 里没有第 %s 课" % n); sys.exit(1)
    lj = os.path.join(LESSONS, slug + ".json")
    d = load(lj)
    oj = os.path.join(ROOT, "work_ocr", "%s.jsonl" % n)
    if not os.path.exists(oj):
        print("缺 %s，先跑 ocr_subs.py" % oj); sys.exit(1)
    rows = [json.loads(x) for x in io.open(oj, encoding="utf-8") if x.strip()]
    # ocr_subs.py 现在写的是 {"t":…, "txt":"EN | CN"}；老文件可能是 {"t":…,"en":…}
    lines = []
    for x in rows:
        raw = x.get("txt") or x.get("en") or ""
        if not raw.strip():
            continue
        en = raw.split("|")[0].strip() if "|" in raw else raw.strip()
        if en:
            lines.append({"t": x["t"], "en": en})
    if len(lines) < SEG_N:
        print("OCR 只拿到 %d 行，少于 %d 段" % (len(lines), SEG_N)); sys.exit(1)
    step = len(lines) / SEG_N
    segs, cuts = [], []
    for i in range(SEG_N):
        a, b = int(round(i * step)), int(round((i + 1) * step))
        grp = lines[a:b] or [lines[min(a, len(lines) - 1)]]
        en = " ".join(x["en"].strip() for x in grp)
        segs.append(en)
        cuts.append([round(max(0.0, grp[0]["t"] - 0.30), 2), round(grp[-1]["t"] + 3.0, 2)])
    p2 = []
    for i, en in enumerate(segs, 1):
        if i % 3 == 1:
            p2.append({"type": "day", "id": "d%d" % (((i - 1) // 3) + 1),
                       "t": "Day %d｜TODO" % (((i - 1) // 3) + 1)})
        p2.append({"type": "seg", "no": "%02d" % i, "ti": "TODO",
                   "audio": "seg%02d.mp3" % i, "slow": "seg%02d_slow.mp3" % i,
                   "en": en, "cn": "TODO"})
    d["part2"] = p2
    d["cuts"] = cuts
    save(lj, d)
    print("✓ %s 的 part2 已按 OCR 行 9 等分填入初稿" % slug)
    print("  接着跑: python tools/rebuild_all.py %s   （reseg → apply_p2 → 媒体 → 渲染）" % n)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "add":
        cmd_add()
    elif cmd == "fill":
        cmd_fill()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
