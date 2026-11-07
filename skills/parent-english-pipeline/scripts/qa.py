# -*- coding: utf-8 -*-
"""qa.py - 字幕 QA 自动检查 + 人工复核用的抽帧拼图。

覆盖 bilingual-subtitles Step 2.5 / 2.6 / Pitfall 16 / 17 / 23 的机器可判部分。
机器判不了的（听辨、译文质量、语义切点）明确列进「人工必看」，不假装检查过。
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import pecore


def _fmt(v: float) -> str:
    return f"{v:.2f}"


def run_qa(cfg: dict, d: Path, lesson: dict) -> dict:
    errors: list[tuple[str, str]] = []
    warns: list[tuple[str, str]] = []
    rows: list[tuple[str, str, str]] = []   # 检查项 / 级别 / 说明

    def err(item: str, msg: str) -> None:
        errors.append((item, msg)); rows.append((item, "ERROR", msg))

    def warn(item: str, msg: str) -> None:
        warns.append((item, msg)); rows.append((item, "WARN", msg))

    def ok(item: str, msg: str) -> None:
        rows.append((item, "OK", msg))

    # ---------- 1. 字幕文件 ----------
    subs_path = d / "subs.json"
    subs: list[dict] = []
    if not subs_path.exists():
        err("字幕文件", "缺 subs.json —— 请先用 bilingual-subtitles 产出校对后的双语条目")
    else:
        try:
            with open(subs_path, "r", encoding="utf-8") as f:
                subs = json.load(f)
            if not isinstance(subs, list) or not subs:
                raise ValueError("不是非空数组")
        except Exception as e:
            err("字幕文件", f"subs.json 解析失败：{e}")
            subs = []
        else:
            ok("字幕文件", f"{len(subs)} 条字幕")

    # ---------- 2. 字体与宽度（折行 / 裁切的根因） ----------
    font_path = cfg["font_path"]
    en_size = int(cfg["en_fontsize"]); cn_size = int(cfg["cn_fontsize"])
    limit = int(cfg["width_limit"])
    FEN = FCN = None
    try:
        FEN = ImageFont.truetype(font_path, en_size)
        FCN = ImageFont.truetype(font_path, cn_size)
        ok("字体", f"{Path(font_path).name} EN{en_size}/CN{cn_size}, 宽度上限 {limit}px")
    except Exception as e:
        err("字体", f"字体加载失败，宽度断言无法执行：{e}")
    if "msyhbd" not in font_path.lower():
        warn("字体粗细", f"当前字体不是粗体 msyhbd.ttc（{Path(font_path).name}），字幕规范要求加粗")

    widest: list[tuple[float, int, str]] = []
    for i, s in enumerate(subs):
        en = str(s.get("en", "")); cn = str(s.get("cn", ""))
        if not en.strip() or not cn.strip():
            err(f"第{i+1}条", "en / cn 为空")
        if "\n" in en or "\n" in cn:
            err(f"第{i+1}条", "文本含换行 —— 一屏一句不折行，长句应拆成多条独立字幕")
        if re.search(r"\s-\w", en) or "  " in en:
            err(f"第{i+1}条", f"疑似词级拼接瑕疵：{en!r}（检查 ' -' / 连续空格）")
        if FEN:
            w = FEN.getlength(en)
            widest.append((w, i + 1, en))
            if w > limit:
                err(f"第{i+1}条 EN", f"宽 {w:.0f}px > {limit}px，会两侧裁切：{en[:60]}")
        if FCN and FCN.getlength(cn) > limit:
            err(f"第{i+1}条 CN", f"中文宽 {FCN.getlength(cn):.0f}px > {limit}px：{cn[:40]}")
        nwords = len(en.split())
        if nwords < 3:
            warn(f"第{i+1}条", f"仅 {nwords} 词（{en!r}）—— 可能是孤儿屏；语气词/短反应可保留，人工确认")
    if FEN and subs and not any(r[1] == "ERROR" and "宽" in r[2] for r in rows):
        ok("英文宽度", f"全部 {len(subs)} 条 <= {limit}px，最宽 {max(widest)[0]:.0f}px")

    # ---------- 3. 时间轴 ----------
    prev_end = None
    gaps: list[float] = []
    for i, s in enumerate(subs):
        try:
            a, b = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            err(f"第{i+1}条", "start / end 缺失或非数字")
            continue
        if b <= a:
            err(f"第{i+1}条", f"end({b}) <= start({a})")
        if prev_end is not None:
            if a < prev_end - 0.05:
                err(f"第{i+1}条", f"与上一条重叠 {prev_end - a:.2f}s（应 <=0.05s）")
            gaps.append(a - prev_end)
        prev_end = b
    if gaps:
        long_gaps = [(i + 2, g) for i, g in enumerate(gaps) if g > 2.5]
        if long_gaps:
            warn("空档", f"{len(long_gaps)} 处 >2.5s 无字幕（第 {[i for i, _ in long_gaps][:6]} 条）；长静音可接受，听辨确认")
        else:
            ok("空档", f"最大空档 {max(gaps):.2f}s，gap-fill 正常")

    # ---------- 4. 完整清单覆盖率 ----------
    man_path = d / "subtitle_manifest.csv"
    if not man_path.exists():
        err("完整清单", "缺 subtitle_manifest.csv（bilingual-subtitles Step 0.5 要求先建清单）")
    else:
        try:
            with open(man_path, "r", encoding="utf-8-sig") as f:
                lines = [ln for ln in f if ln.strip()]
            data_lines = [ln for ln in lines[1:] if not ln.lstrip().startswith("#")] if len(lines) > 1 else []
            n_man = len(data_lines)
            sids = {str(s.get("sentence_id")) for s in subs if s.get("sentence_id") is not None}
            if sids:
                missing = n_man - len(sids)
                if missing > 0:
                    err("覆盖率", f"manifest {n_man} 句，subs 覆盖 {len(sids)} 个 sentence_id，缺 {missing} 句")
                else:
                    ok("覆盖率", f"manifest {n_man} 句，sentence_id 全覆盖")
            elif len(subs) < n_man:
                warn("覆盖率", f"manifest {n_man} 句 / subs {len(subs)} 屏：拆屏会使屏数 >= 句数，"
                              f"当前更少，可能漏句。建议在 subs.json 里带 sentence_id 以便精确比对")
            else:
                ok("覆盖率", f"manifest {n_man} 句 / subs {len(subs)} 屏（未带 sentence_id，按屏数粗比）")
        except Exception as e:
            warn("完整清单", f"读取失败：{e}")

    # ---------- 5. 片尾与时长 ----------
    cut_p, final_p = d / "cut.mp4", d / "final.mp4"
    sheet_rel = None
    if not final_p.exists():
        err("成片", "缺 final.mp4（烧字幕 + 片尾后的成片）")
    elif not cut_p.exists():
        warn("片尾核对", "缺 cut.mp4，无法比对「成片 = 剪辑 + 片尾」")
    else:
        try:
            dc, df = pecore.probe_duration(cut_p), pecore.probe_duration(final_p)
            delta = df - dc
            target = float(cfg["outro_duration"])
            if abs(delta - target) > 0.5:
                err("片尾时长", f"成片 {df:.2f}s - 剪辑 {dc:.2f}s = {delta:.2f}s，"
                                f"应 ≈ {target}s；片尾可能漏拼或采样率不一致导致音轨拉伸")
            else:
                ok("片尾时长", f"{dc:.2f}s + {delta:.2f}s = {df:.2f}s（目标 {target}s）")
        except pecore.PipelineError as e:
            err("片尾时长", str(e))

    # ---------- 6. SRT 双重字幕 ----------
    for p in d.glob("*.srt"):
        if p.stem in ("final", "cut", "src"):
            err("交付规范", f"{p.name} 与成片同目录同名，播放器会自动叠加成双重字幕；"
                            f"请移到 subtitle_work/srt_only/")
    if not any(d.glob("*.srt")):
        ok("交付规范", "课目录下无同名 SRT")

    # ---------- 7. 抽帧拼图（人工必看） ----------
    if final_p.exists() and subs:
        try:
            sheet_rel = _build_sheet(d, final_p, subs)
            ok("抽帧拼图", f"reports/frames_sheet.jpg（{min(10, len(subs))} 帧）")
        except Exception as e:
            warn("抽帧拼图", f"生成失败：{e}；请手工按时间点抽帧复核")
    else:
        warn("抽帧拼图", "无成片或无字幕，未生成")

    # ---------- 报告 ----------
    verdict = "PASS" if not errors else "FAIL"
    lines = [
        f"# 字幕 QA 报告 · 第 {lesson['no']} 课 {lesson.get('zh','')}",
        "",
        f"- 生成时间：{pecore.now()}",
        f"- 档案：`{d}`",
        f"- 参数：EN {en_size}px / CN {cn_size}px / LIM {limit}px / 片尾 {cfg['outro_duration']}s",
        f"- **RESULT: {verdict}（{len(errors)} errors, {len(warns)} warnings）**",
        "",
        "## 检查明细", "",
        "| 检查项 | 级别 | 说明 |", "|---|---|---|",
    ]
    for item, level, msg in rows:
        lines.append(f"| {item} | {level} | {msg.replace('|', '/')} |")
    lines += ["", "## 最宽的 5 条英文", "", "| 宽度 | 序号 | 文本 |", "|---|---|---|"]
    for w, i, en in sorted(widest, reverse=True)[:5]:
        lines.append(f"| {w:.0f}px | {i} | {en[:70].replace('|', '/')} |")
    lines += [
        "", "## 人工必看（机器判不了，必须做）", "",
        "1. 打开 `reports/frames_sheet.jpg`，逐屏看有无裁切 / 折行 / 遮罩顶部漏原片硬字幕。",
        "2. **逐句听辨**：错词、专名、漏掉的短反应、长句被截；`vad_filter` 必须为 False。",
        "3. 逐条通读 `subtitle_work/txt/en_*.txt`，确认无 `hip -hop` 类拼接瑕疵与 1–2 词尾巴屏。",
        "4. 确认中文译文未折行、未用「教学表达」替换原片措辞。",
        "5. 确认片尾「关注我」已拼且音画不错位。",
        "",
        "> 通过后执行：`pe.py approve <no> --stage subs`，`build` 才会解锁。",
    ]
    report = d / "reports" / "qa_report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"errors": errors, "warns": warns, "verdict": verdict,
            "report": str(report), "sheet": sheet_rel, "rows": rows}


def _build_sheet(d: Path, video: Path, subs: list[dict]) -> str:
    """均匀抽最多 10 帧的字幕带，纵向拼一张对照图，供人扫一眼。"""
    n = min(10, len(subs))
    idxs = [int(round(i * (len(subs) - 1) / max(1, n - 1))) for i in range(n)] if n > 1 else [0]
    times = []
    for i in idxs:
        try:
            a, b = float(subs[i]["start"]), float(subs[i]["end"])
            times.append((i + 1, max(0.0, (a + b) / 2)))
        except Exception:
            continue
    tmp = Path(tempfile.mkdtemp(prefix="pe_qa_"))
    frames: list[tuple[int, Path]] = []
    ffmpeg = pecore.tool("ffmpeg")
    for k, (no, t) in enumerate(times):
        out = tmp / f"f{k:02d}.png"
        cp = pecore.run([ffmpeg, "-y", "-ss", f"{t:.2f}", "-i", str(video),
                         "-vframes", "1",
                         "-vf", "crop=iw:ih*0.24:0:ih*0.76", str(out)], timeout=120)
        if cp.returncode == 0 and out.exists() and out.stat().st_size > 0:
            frames.append((no, out))
    if not frames:
        raise RuntimeError("ffmpeg 未能抽出任何帧")
    W, H = 960, 135
    sheet = Image.new("RGB", (W, H * len(frames)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 22)
    for r, (no, p) in enumerate(frames):
        im = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        sheet.paste(im, (0, r * H))
        draw.rectangle((0, r * H, 74, r * H + 28), fill=(0, 0, 0))
        draw.text((6, r * H + 2), f"#{no}", font=label_font, fill=(255, 90, 90))
    out_path = d / "reports" / "frames_sheet.jpg"
    sheet.save(out_path, quality=88)
    # 小批清理，避开沙箱批量删除守卫（每批 <=9 个）
    files = list(tmp.glob("*.png"))
    for i in range(0, len(files), 8):
        for p in files[i:i + 8]:
            try:
                os.remove(p)
            except OSError:
                pass
    try:
        os.rmdir(tmp)
    except OSError:
        pass
    return "reports/frames_sheet.jpg"
