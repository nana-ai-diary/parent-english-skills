# -*- coding: utf-8 -*-
"""全系列重建：reseg -> apply_p2 -> build_media -> build_lesson，最后刷目录。

用法:
  python tools/rebuild_all.py                # 全部
  python tools/rebuild_all.py 19 20 26       # 指定几课
  python tools/rebuild_all.py --cuts-only    # 只改切点时：不重编码视频，只重切分段音频

说明（无烧录字幕 / 手写课程）:
  若某课 lesson JSON 标了 "manual": true，或 tools/p2/<n>.json 里写了 {"manual":true}，
  则跳过 reseg + apply_p2（不跑 OCR 对齐），直接用 lesson JSON 里手写的 part2/cuts
  去 build_media + build_lesson。这样没有烧录字幕的视频也能走通整条流水线。
"""
import io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "tools")
PY = sys.executable or "python"


def sh(args, quiet=False):
    p = subprocess.run([PY, "-B"] + args, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if not quiet and out:
        print(out, flush=True)
    if p.returncode != 0:
        print("!! 失败(%d): %s\n%s" % (p.returncode, " ".join(args), err[-500:]), flush=True)
    return p.returncode == 0


def is_manual(n):
    p2 = os.path.join(BASE, "p2", "%s.json" % n)
    if os.path.exists(p2):
        try:
            if json.load(io.open(p2, encoding="utf-8")).get("manual"):
                return True
        except Exception:
            pass
    for f in os.listdir(os.path.join(BASE, "lessons")):
        if f.startswith(n + "-"):
            try:
                if json.load(io.open(os.path.join(BASE, "lessons", f), encoding="utf-8")).get("manual"):
                    return True
            except Exception:
                pass
            break
    return False


def main():
    args = sys.argv[1:]
    cuts_only = "--cuts-only" in args
    args = [a for a in args if not a.startswith("--")]
    lessons = sorted(f for f in os.listdir(os.path.join(BASE, "lessons")) if f.endswith(".json"))
    picks = args or [f[:2] for f in lessons]
    ok, skip = [], []
    for n in picks:
        slug_files = [f for f in lessons if f.startswith(n + "-")]
        if not slug_files:
            print("跳过 %s：找不到 lessons/%s-*.json" % (n, n), flush=True)
            skip.append(n)
            continue
        slug = slug_files[0][:-5]
        manual = is_manual(n)
        if not manual:
            ocr = os.path.join(ROOT, "work_ocr", "%s.txt" % n)
            if not os.path.exists(ocr) or os.path.getsize(ocr) < 300:
                print("跳过 %s：缺少 work_ocr/%s.txt（无烧录字幕请加 manual 或先跑 ocr_subs）" % (n, n), flush=True)
                skip.append(n)
                continue
            print("=" * 70, "\n>>> 第 %s 课  %s" % (n, slug), flush=True)
            sh(["tools/reseg.py", n])
            if not sh(["tools/apply_p2.py", n, "--write"]):
                skip.append(n)
                continue
        else:
            print("=" * 70, "\n>>> 第 %s 课  %s  [manual：跳过 OCR 对齐]" % (n, slug), flush=True)
        step = (["tools/rebuild_audio.py", n] if cuts_only
                else ["tools/build_media.py", "tools/lessons/" + slug_files[0]])
        if not sh(step, quiet=cuts_only):
            skip.append(n)
            continue
        sh(["tools/build_lesson.py", "tools/lessons/" + slug_files[0]])
        ok.append(n)
    print("\n完成: %s" % " ".join(ok))
    if skip:
        print("跳过: %s" % " ".join(skip))
    sh(["tools/build_catalog.py"])


if __name__ == "__main__":
    main()
