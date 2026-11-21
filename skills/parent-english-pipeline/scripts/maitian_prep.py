# -*- coding: utf-8 -*-
"""maitian_prep.py — 把亲子英语一课组装成麦田发布工程（本地，不上传、不填表、不发帖）。

输入：
  lesson.json / xhs.txt / final.mp4 / subtitle_work/srt_only/*.srt
  + 豆包出的 3:4 封面（--cover，缺省用 html/img/poster.jpg）

产出（默认 <MAITIAN_DIR>/发布工程/<序号>.<主题>/）：
  成片.mp4            final.mp4 无损重封装，moov 前置（faststart）
  字幕.srt            从 srt_only 复制
  发布素材.md         按麦田 maitian-publish 模板，写小红书 + 抖音，可选 B站（均为手动平台）
  封面/cover-3x4.png  豆包图（或 poster 兜底）
  封面/cover-4x3.png  3:4 居中裁切成 4:3
  封面/cover-16x9.jpg 4:3 补模糊背景到 16:9
  publish.json        由麦田 tools/make-publish.mjs 生成并 validate

安全：本脚本**只写本地工程目录**；不启 Chrome、不连平台、不调 hub plan/run。
      上传视频 / 图片 / 填文案由麦田 `hub run` 完成，且国内四家填好就停，
      最后「发布」永远由人点。跑完本脚本后按提示人工确认再决定要不要 run。

用法:
  python maitian_prep.py 55 --cover "C:/path/豆包封面.png"
  python maitian_prep.py 55                      # 用 html/img/poster.jpg 兜底
  python maitian_prep.py 55 --out D:/发布工程 --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pecore
import xhs_check

DEFAULT_ROOT = Path(r"<PROJECT_ROOT>")   # 项目根，pecore 自己拼 lessons/
DEFAULT_OUT = Path(r"<MAITIAN_OUT>")
PUBLISHER = Path(r"<MAITIAN_PUBLISHER>")
NODE = "node"


def emit(s: str = "") -> None:
    print(s, flush=True)


def run(cmd: list[str], *, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    emit(f"[RUN] {' '.join(str(x) for x in cmd)}")
    cp = subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                        timeout=timeout, encoding="utf-8", errors="replace")
    if cp.stdout.strip():
        emit(cp.stdout.strip())
    if cp.returncode and check:
        raise RuntimeError(f"命令失败 rc={cp.returncode}: {cp.stderr.strip()[-800:]}")
    return cp


def pick_srt(d: Path) -> Path | None:
    cands = sorted((d / "subtitle_work" / "srt_only").glob("*.srt"))
    return cands[0] if cands else None


def prepare_video(src: Path, dst: Path) -> None:
    """无损重封装，moov 前置。麦田 validate 会查 faststart，否则小红书报无视频流。"""
    run([pecore.tool("ffmpeg"), "-v", "error", "-y", "-i", str(src),
         "-c", "copy", "-movflags", "+faststart", str(dst)], timeout=600)


def prepare_covers(src: Path, cover_dir: Path) -> None:
    from PIL import Image, ImageFilter
    cover_dir.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    # 归一化到 3:4
    w, h = im.size
    tw, th = 1080, 1440
    if (w / h) > (tw / th):  # 太宽，左右裁
        nw = int(h * tw / th)
        im = im.crop(((w - nw) // 2, 0, (w + nw) // 2, h))
    elif (w / h) < (tw / th):  # 太高，上下裁
        nh = int(w * th / tw)
        im = im.crop((0, (h - nh) // 2, w, (h + nh) // 2))
    im = im.resize((tw, th), Image.LANCZOS)
    im.save(cover_dir / "cover-3x4.png")

    # 4:3：从 3:4 中间裁一条 1080x810
    im.crop((0, (th - 810) // 2, tw, (th + 810) // 2)).save(cover_dir / "cover-4x3.png")

    # 16:9：4:3 内容放到 1920x1080 模糊底上（麦田 skill 的 ffmpeg 等价实现）
    base = im.crop((0, (th - 810) // 2, tw, (th + 810) // 2)).resize((1920, 1080), Image.LANCZOS)
    bg = base.filter(ImageFilter.GaussianBlur(40))
    fg = im.crop((0, (th - 810) // 2, tw, (th + 810) // 2))
    r = 1920 / fg.width
    fg = fg.resize((1920, int(fg.height * r)), Image.LANCZOS)
    if fg.height > 1080:
        fg = fg.crop((0, (fg.height - 1080) // 2, 1920, (fg.height + 1080) // 2))
    bg.paste(fg, (0, (1080 - fg.height) // 2))
    bg.save(cover_dir / "cover-16x9.jpg", quality=92)
    emit(f"[封面] 3:4 / 4:3 / 16x9 已生成（源 {src.name}）")


def build_md(lesson: dict, parsed: dict, title: str, *, bili: bool = False,
             schedule: str = "") -> str:
    no, zh = lesson["no"], lesson.get("zh", "")
    # 2026-11-21 用户改版：
    #   1) 基础 tag 里「幼儿英语启蒙」统一写成「英语启蒙」；
    #   2) 平台活动 tag 只在下游加，不写进 xhs.txt；
    #   3) B站标题/正文与小红书、抖音完全一致，分区交给适配器默认「亲子」。
    base_topics = ["英语启蒙" if t == "幼儿英语启蒙" else t for t in parsed["topics"]]
    base_line = " ".join("#" + t for t in base_topics)
    xhs_topics = base_topics + ["RED11月精选作者评选"]
    douyin_topics = base_topics + ["抖音精选app征稿中"]
    xhs_topic_line = " ".join("#" + t for t in xhs_topics)
    douyin_topic_line = " ".join("#" + t for t in douyin_topics)
    body = parsed["body"].strip()
    # 话题单独一行，麦田 splitTopics 才会拆进 topics（不计入正文字数）
    xhs_body = body + ("\n\n" + xhs_topic_line if xhs_topic_line else "")
    douyin_body = body + ("\n\n" + douyin_topic_line if douyin_topic_line else "")
    comments = parsed["comments"]

    lines = [
        f"# 亲子英语启蒙跟读 · 第 {no} 期｜{zh}",
        "",
        f"> 序号：{no}",
    ]
    if schedule:
        lines += [f"> 定时发布：{schedule}"]
    lines += [""]
    if bili:
        lines += [
            "## 三、B站",
            "**标题：**",
            title,
            "**简介：**",
            body,
            "**标签：**",
            base_line,
            "**分区：**",
            "亲子",
            "",
        ]
    # 三个平台共用同一个标题；小红书/抖音正文各自带一个平台活动 tag。
    lines += [
        "## 四、小红书",
        "**标题：**",
        title,
        "**正文：**",
        xhs_body,
        "",
        "## 五、抖音",
        "**标题：**",
        title,
        "**正文：**",
        douyin_body,
        "**合集：**",
        "亲子英语口语·100个场景合集",
        "**保存权限：**",
        "允许",
        "",
    ]
    if comments:
        lines += ["## 置顶评论（人工发）", "\n".join(comments), ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("no", help="课号")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--cover", default="", help="豆包出的 3:4 封面路径")
    ap.add_argument("--bili", action="store_true", help="同时生成 B站段（与小红书/抖音同标题同正文，分区默认亲子）")
    ap.add_argument("--schedule", default="", help='定时发布时间，格式 "YYYY-MM-DD HH:mm"（要晚于现在 2 小时、14 天以内）')
    ap.add_argument("--dry-run", action="store_true", help="只打印将做的事，不写文件")
    a = ap.parse_args()

    root = Path(a.root)
    d = pecore.find_lesson_dir({"project_root": str(root)}, a.no)
    lesson = pecore.read_lesson(d)
    no, zh = lesson["no"], lesson.get("zh", "")

    # 1) 文案闸门（先卡字数，不合格不往下走）
    txt = d / "xhs.txt"
    ok, problems, stats = xhs_check.check_file(txt)
    if not ok:
        emit(f"[BLOCK] 文案字数不合格，先改 {txt}（麦田会拒收）：")
        for p in problems:
            emit(f"  - {p}")
        emit("  改完重跑本命令；可用 `pe.py xhs " + str(no) + "` 单独体检。")
        return 1
    parsed = xhs_check.parse_xhs(txt.read_text(encoding="utf-8", errors="replace"))
    title = parsed["titles"][0]
    emit(f"[文案] PASS 标题「{title}」({len(title)}字) / 正文 {stats['body_chars']}字")

    final = d / "final.mp4"
    if not final.exists():
        emit(f"[BLOCK] 缺 {final}")
        return 1
    cover = Path(a.cover) if a.cover else d / "html" / "img" / "poster.jpg"
    if not cover.exists():
        emit(f"[BLOCK] 缺封面 {cover}；请把豆包出的 3:4 图路径传给 --cover")
        return 1
    srt = pick_srt(d)

    proj = Path(a.out) / f"{no}.{zh}"
    emit(f"\n[工程] {proj}")
    emit(f"  成片.mp4          <- {final}（faststart 重封装）")
    emit(f"  字幕.srt          <- {srt.name if srt else '(无)'}")
    emit(f"  封面/cover-3x4.png <- {cover}")
    emit(f"  发布素材.md        <- {txt.name}")
    plats = "B站 / 小红书 / 抖音" if a.bili else "小红书 / 抖音"
    emit(f"  平台              : {plats}（均 manual，填好你自己点发布）")
    if a.schedule:
        emit(f"  定时发布          : {a.schedule}（适配器会打开定时开关并填时间）")
    emit("  外部副作用        : 无（不启 Chrome、不上传、不填表、不发帖）")
    if a.dry_run:
        emit("\n[DRY-RUN] 未写任何文件")
        return 0

    proj.mkdir(parents=True, exist_ok=True)
    (proj / "封面").mkdir(exist_ok=True)
    prepare_video(final, proj / "成片.mp4")
    if srt:
        shutil.copy2(srt, proj / "字幕.srt")
    prepare_covers(cover, proj / "封面")
    (proj / "发布素材.md").write_text(
        build_md(lesson, parsed, title, bili=a.bili, schedule=a.schedule), encoding="utf-8")
    shutil.copy2(txt, proj / "原-xhs.txt")

    # 调麦田的生成器 + 校验器（本地，不联网）
    mk = PUBLISHER / "tools" / "make-publish.mjs"
    va = PUBLISHER / "tools" / "validate.mjs"
    if not mk.exists():
        emit(f"[WARN] 没找到 {mk}，跳过 publish.json 生成（工程文件已就绪）")
        return 0
    run([NODE, str(mk), str(proj / "发布素材.md"), str(proj)], timeout=120)

    # Windows 修补：make-publish.mjs 用 "封面/cover-3x4.png"（正斜杠）匹配
    # path.relative() 出的 "封面\cover-3x4.png"（反斜杠），必然落空 → covers={}。
    # 这里按实际存在的文件补回 covers，并按平台补上封面引用（不动麦田源码）。
    pj_path = proj / "publish.json"
    if pj_path.exists():
        pj = json.loads(pj_path.read_text(encoding="utf-8"))
        cov = {}
        for key, name in (("3x4", "cover-3x4.png"), ("4x3", "cover-4x3.png"),
                          ("16x9", "cover-16x9.jpg")):
            if (proj / "封面" / name).exists():
                cov[key] = f"封面/{name}"
        if cov and not pj.get("covers"):
            pj["covers"] = cov
            for pid, keys in (("xhs", ["3x4"]), ("douyin", ["4x3", "3x4"]),
                              ("channels", ["4x3", "3x4"]),
                              ("bilibili", ["4x3"]), ("youtube", ["16x9"])):
                pl = pj.get("platforms", {}).get(pid)
                if pl and not pl.get("covers"):
                    pl["covers"] = [k for k in keys if k in cov]
            pj_path.write_text(json.dumps(pj, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
            emit(f"[封面修补] 已写回 covers={list(cov)}（绕开麦田 Windows 路径匹配问题）")

    cp = run([NODE, str(va), str(proj)], check=False, timeout=120)
    if cp.returncode:
        emit("[BLOCK] 麦田校验未通过 —— 工程已生成但不可跑 hub run")
        return 1

    emit("\n[DONE] 麦田工程已就绪（本地）。")
    emit("下一步（都在你确认后做，国内平台最后一下永远你点）：")
    bili_hint = "，B站用 启动B站专用Chrome.bat 扫码" if a.bili else ""
    emit(f"  1) 双击 <MAITIAN_DIR>/2-login.bat 登录小红书 / 抖音{bili_hint}，关掉")
    emit(f"  2) 双击 <MAITIAN_DIR>/3-doctor.bat 确认登录态与上传页 OK")
    emit(f'  3) cd /d "<MAITIAN_HUB>" && node src/hub.mjs plan "{proj}"')
    emit(f'  4) node src/hub.mjs run "{proj}"   ← 自动上传视频/封面并填文案，填好就停')
    emit("  5) 到创作中心检查文案/封面/定时，自己点「发布」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
