# -*- coding: utf-8 -*-
"""全系列重建：reseg -> apply_p2 -> build_media -> build_lesson，最后刷目录。

用法:
  python tools/rebuild_all.py                # 全部（有 OCR 的才做）
  python tools/rebuild_all.py 19 20 26       # 指定几课
  python tools/rebuild_all.py --cuts-only    # 只改切点时用：不重编码视频，
                                             # 只重切分段音频（rebuild_audio.py）
"""
import io, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def main():
    args = sys.argv[1:]
    cuts_only = "--cuts-only" in args
    args = [a for a in args if not a.startswith("--")]
    lessons = sorted(f for f in os.listdir(os.path.join(ROOT, "tools", "lessons")) if f.endswith(".json"))
    picks = args or [f[:2] for f in lessons]
    ok, skip = [], []
    for n in picks:
        ocr = os.path.join(ROOT, "work_ocr", "%s.txt" % n)
        if not os.path.exists(ocr) or os.path.getsize(ocr) < 300:
            skip.append(n)
            continue
        slug = [f for f in lessons if f.startswith(n + "-")]
        if not slug:
            skip.append(n)
            continue
        print("=" * 70, "\n>>> 第 %s 课  %s" % (n, slug[0][:-5]), flush=True)
        sh(["tools/reseg.py", n])
        if not sh(["tools/apply_p2.py", n, "--write"]):
            skip.append(n)
            continue
        step = (["tools/rebuild_audio.py", n] if cuts_only
                else ["tools/build_media.py", "tools/lessons/" + slug[0]])
        if not sh(step, quiet=cuts_only):
            skip.append(n)
            continue
        sh(["tools/build_lesson.py", "tools/lessons/" + slug[0]])
        ok.append(n)
    print("\n完成: %s" % " ".join(ok))
    if skip:
        print("跳过: %s" % " ".join(skip))
    sh(["tools/build_catalog.py"])


if __name__ == "__main__":
    main()
