# -*- coding: utf-8 -*-
"""pe.py - 亲子英语单课流水线编排器。

不假成功：未接通的创作步骤标 blocked 并给出精确待办；外部命令错误一律归一化。
用法见同目录 ../SKILL.md。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pecore
import qa

BANNER = "parent-english-pipeline"


def emit(msg: str = "") -> None:
    print(msg, flush=True)


def todo(stage: str, lines: list[str]) -> None:
    emit(f"\n[待办 · {stage}] 这步需要人或下游 skill 完成：")
    for ln in lines:
        emit(f"  - {ln}")


# --------------------------------------------------------------------------- helpers
def open_lesson(cfg: dict, no: str) -> tuple[Path, dict]:
    d = pecore.find_lesson_dir(cfg, no)
    return d, pecore.read_lesson(d)


def finish(cfg: dict, d: Path, lesson: dict, stage: str, state: str,
           note: str = "", verbose: bool = True) -> None:
    pecore.set_stage(lesson, stage, state, note)
    lesson["artifacts"] = pecore.scan_artifacts(d)
    pecore.write_lesson(d, lesson)
    if verbose:
        mark = {"done": "OK", "blocked": "BLOCKED", "failed": "FAILED",
                "skipped": "SKIP", "pending": "PENDING"}[state]
        emit(f"[{mark}] {stage} · {pecore.STAGE_LABEL.get(stage, stage)}" + (f" — {note}" if note else ""))


def skip_if_done(lesson: dict, stage: str, force: bool) -> bool:
    if not force and pecore.stage_state(lesson, stage) == "done":
        emit(f"[SKIP] {stage} 已完成（--force 可重跑）")
        return True
    return False


def status_lines(cfg: dict, d: Path, lesson: dict) -> list[str]:
    out = [f"第 {lesson['no']} 课 · {lesson.get('zh','')}   [{d}]",
           f"来源: YouTube {lesson.get('by') or '（未登记）'}",
           f"HTML : {cfg.get('shared_site_index', '(未配置)')}",
           "", f"{'#':<3}{'阶段':<10}{'状态':<10}{'时间':<21}备注",
           "-" * 78]
    for i, s in enumerate(pecore.STAGES, 1):
        rec = lesson["stages"].get(s, {})
        out.append(f"{i:<3}{s:<10}{rec.get('state','pending'):<10}"
                   f"{(rec.get('ts') or '-'):<21}{rec.get('note','')[:36]}")
    a = lesson.get("approvals", {})
    out += ["-" * 78,
            f"闸门  subs : {'PASS @' + a['subs'] if a.get('subs') else '未通过 (build 被拦)'}",
            f"闸门  final: {'PASS @' + a['final'] if a.get('final') else '未通过 (publish 被拦)'}",
            ""]
    stale = []
    for s in pecore.STAGES:
        found, missing = pecore.check_expected(s, d)
        present = [k for k, v in found.items() if v]
        if present or missing:
            out.append(f"  {s:<9} 有: {', '.join(present) or '-'}"
                       + (f"  | 缺: {', '.join(missing)}" if missing else ""))
        if (lesson["stages"].get(s, {}).get("state") == "pending"
                and present and not missing):
            stale.append(s)
    if stale:
        out += ["", f"提示：{', '.join(stale)} 产物已齐但状态仍是 pending —— "
                f"手工完成的用 `pe.py mark {lesson['no']} <stage> --done` 登记"]
    return out


def html_check(d: Path) -> tuple[list[str], list[str]]:
    """轻量 HTML 体检：资源存在 / div 配平 / 七个 Part 齐全。"""
    p = d / "html" / "index.html"
    probs: list[str] = []
    notes: list[str] = []
    if not p.exists():
        return ["缺 html/index.html"], []
    h = p.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', h):
        ref = m.group(1)
        if ref.startswith(("http:", "https:", "data:", "#", "javascript:")):
            continue
        rel = ref.split("#")[0].split("?")[0]
        if rel and not (p.parent / rel).exists():
            probs.append(f"资源不存在: {rel}")
    class Counter(HTMLParser):
        def __init__(self):
            super().__init__(); self.div = 0; self.parts = set()
        def handle_starttag(self, tag, attrs):
            if tag == "div": self.div += 1
        def handle_endtag(self, tag):
            if tag == "div": self.div -= 1
    c = Counter(); c.feed(h)
    if c.div != 0:
        probs.append(f"div 标签不配平 (差 {c.div})")
    found_parts = set(re.findall(r"Part\s*([1-7])", h))
    if len(found_parts) < 7:
        notes.append(f"HTML 里只见 Part {sorted(found_parts)}，期望 1–7（Part 7 可选，确认是否为有意省略）")
    notes.append(f"HTML {len(h)/1024:.0f} KB，音频/视频相对引用已核对")
    return probs, notes


def suggest_windows(video: Path, target: float = 120.0) -> list[tuple[float, float, float]]:
    """用 silencedetect 找静音中点，枚举接近 target 秒的候选剪辑窗。"""
    cp = pecore.run([pecore.tool("ffmpeg"), "-hide_banner", "-i", str(video),
                     "-af", "silencedetect=noise=-35dB:d=0.4", "-f", "null", "-"], timeout=600)
    text = (cp.stderr or "") + (cp.stdout or "")
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", text)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", text)]
    mids = [((a + b) / 2) for a, b in zip(starts, ends)]
    dur = pecore.probe_duration(video)
    bounds = sorted({0.0, *[m for m in mids if 0 < m < dur], round(dur, 2)})
    cand = []
    for i, a in enumerate(bounds):
        for b in bounds[i + 1:]:
            L = b - a
            if 95.0 <= L <= 145.0:
                score = abs(L - target) + (0 if a > 0 else 8) + (0 if b < dur - 0.5 else 8)
                cand.append((score, a, b))
    cand.sort()
    return [(a, b, b - a) for _, a, b in cand[:3]]


# --------------------------------------------------------------------------- commands
def cmd_new(args, cfg):
    root = pecore.lessons_root(cfg)
    slug = args.slug or f"{int(args.no):02d}-lesson"
    d = root / slug
    if d.exists():
        raise pecore.PipelineError(f"档案已存在，拒绝覆盖：{d}（要重来请先手动移走该目录）")
    pecore.ensure_dirs(d)
    lesson = pecore.new_lesson(cfg, int(args.no), args.zh, args.en or "", args.by or "",
                               args.cat or "", args.age, args.diff, slug, args.url or "")
    pecore.write_lesson(d, lesson)
    finish(cfg, d, lesson, "new", "done", f"slug={slug}")
    emit("\n".join(status_lines(cfg, d, lesson)))
    return 0


def capture_source(d: Path, lesson: dict, cfg: dict, url: str | None = None,
                   *, refetch: bool = False) -> list[str]:
    """来源自动采集：下载时 yt-dlp --write-info-json 落的 src.info.json 就是事实源。
    refetch=True 时用 --dump-single-json 补抓（不下载视频），并允许覆盖已有 by。
    """
    info_p = d / "src.info.json"
    if refetch and url:
        argv = [pecore.tool("yt-dlp"), "--dump-single-json", "--skip-download",
                "--no-warnings", "--no-playlist", "--socket-timeout", "15", "--retries", "0"]
        if cfg.get("youtube_cookies"):
            argv += ["--cookies", cfg["youtube_cookies"]]
        argv.append(url)
        cp = pecore.run(argv, cwd=d, timeout=180,
                        env_extra={"HTTPS_PROXY": cfg.get("outbound_proxy"),
                                   "HTTP_PROXY": cfg.get("outbound_proxy")})
        txt = (cp.stdout or "").strip()
        if cp.returncode == 0 and txt.startswith("{"):
            info_p.write_text(txt, encoding="utf-8")
        else:
            emit(f"[WARN] 来源补抓失败：{((cp.stderr or '') + txt)[-300:]}")
    if not info_p.exists():
        return []
    try:
        info = json.loads(info_p.read_text(encoding="utf-8"))
    except Exception as e:
        emit(f"[WARN] src.info.json 解析失败：{e}")
        return []
    return pecore.apply_source(lesson, pecore.parse_source_info(info), overwrite=refetch)


def source_reminder(lesson: dict) -> str:
    by = lesson.get("by") or ""
    if not by:
        return "[提醒] 来源未登记！`pe.py source <no> --url <链接>` 可自动采集，HTML 里必须写来源"
    return f"[提醒] 本课来源 YouTube {by} —— HTML 页头 srcbar 与页脚版权声明都要写上（用户明确要求）"


def cmd_fetch(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    if skip_if_done(lesson, "fetch", args.force):
        return 0
    src = d / "src.mp4"
    if src.exists() and not args.force:
        changed = capture_source(d, lesson, cfg)
        if changed:
            pecore.write_lesson(d, lesson)
            emit(f"[来源自动采集] {', '.join(changed[:4])}")
        finish(cfg, d, lesson, "fetch", "done", "src.mp4 已就位")
        emit(source_reminder(lesson))
        return 0
    url = args.url or lesson.get("source_url")
    if not url:
        finish(cfg, d, lesson, "fetch", "blocked", "未提供 YouTube 链接")
        todo("fetch", ["`pe.py fetch <no> --url <链接>`，或手工把素材放到：",
                       f"  {src}",
                       "放好后 `pe.py mark <no> fetch --done`；"
                       "手工素材用 `pe.py source <no> --by \"@频道\"` 登记来源"])
        return 0
    argv = [pecore.tool("yt-dlp"), "--no-playlist", "--concurrent-fragments", "4",
            "-f", "bv*[height<=1080]+ba/b[height<=1080]",
            "--merge-output-format", "mp4", "--write-info-json",
            "-o", str(d / "src.%(ext)s")]
    if cfg.get("youtube_cookies"):
        argv += ["--cookies", cfg["youtube_cookies"]]
    argv.append(url)
    emit(f"[RUN] yt-dlp 下载中（同时落 src.info.json 采集来源）…")
    cp = pecore.run(argv, cwd=d, timeout=1800,
                    env_extra={"HTTPS_PROXY": cfg.get("outbound_proxy"),
                               "HTTP_PROXY": cfg.get("outbound_proxy")})
    produced = sorted(d.glob("src.*"))
    mp4 = next((p for p in produced if p.suffix.lower() == ".mp4"), None)
    if cp.returncode != 0 or not mp4:
        finish(cfg, d, lesson, "fetch", "failed", "yt-dlp 未产出 src.mp4")
        raise pecore.PipelineError(f"下载失败 rc={cp.returncode}\n{(cp.stderr or '')[-1200:]}")
    if mp4 != src:
        shutil.move(str(mp4), str(src))
    lesson["source_url"] = url
    changed = capture_source(d, lesson, cfg, url)
    if changed:
        emit("[来源自动采集] " + ", ".join(changed[:5]))
    note = f"{src.stat().st_size/1048576:.1f} MB"
    if lesson.get("by"):
        note += f" | 来源 {lesson['by']}"
    else:
        emit("[WARN] 未取到来源信息，稍后跑 `pe.py source <no> --url <链接>` 补抓")
    finish(cfg, d, lesson, "fetch", "done", note)
    emit(source_reminder(lesson))
    return 0


def cmd_source(args, cfg):
    """查看 / 补抓 / 手工登记来源，写进 lesson.json 供 HTML 的 by 使用。"""
    d, lesson = open_lesson(cfg, args.no)
    changed: list[str] = []
    if args.by:
        by = args.by if args.by.startswith("@") else args.by
        if lesson.get("by") != by:
            lesson["by"] = by
            changed.append(f"by={by}（手工登记）")
    url = args.url or lesson.get("source_url")
    changed += capture_source(d, lesson, cfg, url, refetch=bool(args.url))
    pecore.write_lesson(d, lesson)
    for c in changed:
        emit(f"  [写入] {c}")
    by = lesson.get("by") or "(空)"
    emit(f"[来源] by={by}")
    emit(f"       URL={lesson.get('source_url') or '-'}")
    emit(f"       原标题={lesson.get('source_title') or '-'}")
    emit(source_reminder(lesson))
    return 0


def cmd_cut(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    src = d / "src.mp4"
    if not src.exists():
        raise pecore.PipelineError(f"缺 {src}，先跑 fetch")
    if args.suggest:
        dur = pecore.probe_duration(src)
        wins = suggest_windows(src)
        emit(f"原片 {dur:.1f}s，目标 120s。静音点对齐后的候选区间：")
        if not wins:
            emit("  未找到合适静音边界；建议手工听一遍定 --keep START END")
        for a, b, L in wins:
            emit(f"  --keep {a:.2f} {b:.2f}   ({L:.1f}s)")
        emit("\n定稿后跑 `pe.py cut <no> --keep S E`。剪辑必须在转录/烧字幕之前完成。")
        return 0
    if skip_if_done(lesson, "cut", args.force):
        return 0
    if not args.keep:
        finish(cfg, d, lesson, "cut", "blocked", "未定剪辑区间")
        todo("cut", ["`pe.py cut <no> --suggest` 看候选区间",
                     "`pe.py cut <no> --keep START END` 定稿（重编码，时间轴从 0 起）"])
        return 0
    a, b = float(args.keep[0]), float(args.keep[1])
    if b <= a:
        raise pecore.PipelineError(f"--keep 区间非法：{a} >= {b}")
    out = d / "cut.mp4"
    emit(f"[RUN] ffmpeg 精确裁剪 {a:.2f}–{b:.2f}s …")
    pecore.run([pecore.tool("ffmpeg"), "-y", "-ss", f"{a:.3f}", "-i", str(src),
                "-t", f"{b-a:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                "-movflags", "+faststart", str(out)], timeout=1800, check=True)
    dur = pecore.probe_duration(out)
    lesson["cut"] = {"keep": [a, b], "duration": round(dur, 3)}
    finish(cfg, d, lesson, "cut", "done", f"{dur:.2f}s (源 {a:.2f}–{b:.2f})")
    return 0


def cmd_subs(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    cut = d / "cut.mp4"
    if not cut.exists():
        raise pecore.PipelineError(f"缺 {cut} —— 剪辑未定稿，转录现在跑会白跑")
    if skip_if_done(lesson, "subs", args.force):
        return 0
    tr = d / "transcript.json"
    if not tr.exists() or args.force:
        venv = cfg["python_venv"]
        if not Path(venv).exists():
            raise pecore.PipelineError(f"虚拟环境不存在：{venv}")
        emit(f"[RUN] 全链路唯一一次转录（{cfg['whisper_model']}, word_timestamps, vad_filter=False）…")
        pecore.run([venv, str(Path(__file__).with_name("transcribe_once.py")),
                    str(cut), str(tr), cfg["whisper_model"], cfg["whisper_compute"]],
                   timeout=3600, check=True)
        emit(f"  -> {tr}")
    else:
        emit(f"[SKIP] 转录已有，复用 {tr.name}（不再跑第二次推理）")
    _, missing = pecore.check_expected("subs", d)
    if missing:
        finish(cfg, d, lesson, "subs", "blocked", f"转录完成，字幕创作待办（缺 {len(missing)} 项）")
        todo("subs", ["用 `bilingual-subtitles` skill，依据 transcript.json + 抽帧拼图逐句校对",
                      f"产出 {d / 'subtitle_manifest.csv'}（一句一行，覆盖每句可听见的台词）",
                      f"产出 {d / 'subs.json'}（[{{start,end,en,cn,sentence_id?}}]，end 已 gap-fill）",
                      f"产出 {d / 'final.mp4'}（烧字幕 + 必拼「关注我」片尾）",
                      "SRT 放 subtitle_work/srt_only/，不要与 mp4 同目录同名",
                      "完成后 `pe.py mark <no> subs --done` 再跑 `pe.py qa <no>`"])
        return 0
    finish(cfg, d, lesson, "subs", "done", "四件产物齐备")
    return 0


def cmd_qa(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    result = qa.run_qa(cfg, d, lesson)
    emit(f"\nQA {result['verdict']}: {len(result['errors'])} errors / {len(result['warns'])} warnings")
    for item, msg in result["errors"][:12]:
        emit(f"  ERROR  {item}: {msg}")
    for item, msg in result["warns"][:8]:
        emit(f"  WARN   {item}: {msg}")
    emit(f"\n报告: {result['report']}")
    if result.get("sheet"):
        emit(f"拼图: {d / result['sheet']}  ← 必须人工扫一眼")
    if result["verdict"] == "FAIL":
        finish(cfg, d, lesson, "qa", "failed", f"{len(result['errors'])} 项未通过")
        emit("\n修好后重跑 `pe.py qa <no>`；通过后 `pe.py approve <no> --stage subs`。")
        return 1
    finish(cfg, d, lesson, "qa", "done", f"PASS，{len(result['warns'])} 条警告需人工确认")
    return 0


def cmd_approve(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    stage = args.stage
    if stage not in ("subs", "final"):
        raise pecore.PipelineError("--stage 只能是 subs 或 final")
    need = "qa" if stage == "subs" else "verify"
    if pecore.stage_state(lesson, need) != "done":
        raise pecore.PipelineError(f"不能批准：{need} 阶段尚未 done（当前 "
                                  f"{pecore.stage_state(lesson, need)}）")
    report = d / "reports" / ("qa_report.md" if stage == "subs" else "verify_report.md")
    verdict = "RESULT: PASS" if stage == "subs" else "CONCLUSION: PASS"
    if not report.exists() or verdict not in report.read_text(encoding="utf-8", errors="replace"):
        raise pecore.PipelineError(
            f"不能批准：{report.name} 里没有 `{verdict}`。\n"
            f"  先修完报告里的问题，再重跑 `pe.py {'qa' if stage == 'subs' else 'verify'} {lesson['no']}`")
    lesson["approvals"][stage] = pecore.now()
    pecore.write_lesson(d, lesson)
    emit(f"[APPROVED] {stage} @ {lesson['approvals'][stage]}（已核对 {report.name} = PASS）")
    if stage == "subs":
        emit("build / upload 已解锁。")
    else:
        emit("publish 已解锁（仍不自动发帖）。")
    return 0


def cmd_build(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    pecore.gate(lesson, "subs", "build")
    emit(source_reminder(lesson))
    if skip_if_done(lesson, "build", args.force):
        return 0
    full = d / "html" / "audio" / "full.mp3"
    final = d / "final.mp4"
    if not full.exists() and final.exists():
        emit("[RUN] 从成片抽整视频音轨 full.mp3 …")
        pecore.run([pecore.tool("ffmpeg"), "-y", "-i", str(final), "-vn",
                    "-c:a", "libmp3lame", "-b:a", "128k", "-ar", "44100", "-ac", "1",
                    str(full)], timeout=600, check=True)
    probs, notes = html_check(d)
    _, missing = pecore.check_expected("build", d)
    if missing or probs:
        finish(cfg, d, lesson, "build", "blocked",
               f"缺 {len(missing)} 项产物" + (f" / HTML {len(probs)} 处问题" if probs else ""))
        todo("build", [f"用 `parent-english-html` 生成 {d / 'html/index.html'} 与 {d / 'pdf/'}；"
                       "英文事实源直接用 subs.json，不要跑 ocr_subs.py",
                       f"用 `video-english-xhs` 生成 {d / 'xhs.txt'}，8 句从 subs.json 的完整清单里挑"]
             + [f"缺: {m}" for m in missing]
             + [f"HTML 问题: {p}" for p in probs[:8]]
             + ["完成后 `pe.py mark <no> build --done`"])
        return 0
    finish(cfg, d, lesson, "build", "done",
           f"HTML/MP3/PDF/文案齐备；{'; '.join(notes)[:60]}")
    return 0


def cmd_upload(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    # 上传排在终验之前：核对「上传文件有没有问题」本来就要等文件先传完。
    pecore.gate(lesson, "subs", "upload")
    if pecore.stage_state(lesson, "build") != "done":
        raise pecore.PipelineError("build 尚未 done，不能上传（HTML / PDF / 音频可能不齐）")
    no, zh = lesson["no"], lesson.get("zh", "")
    bundle = d / "upload_bundle"
    bundle.mkdir(parents=True, exist_ok=True)
    delivery = Path(cfg["delivery_dir"])
    final = d / "final.mp4"
    target_mp4 = delivery / f"{no}.{zh}.mp4"
    pdfs = sorted((d / "pdf").glob("*.pdf"))
    mp3 = d / "html" / "audio" / "full.mp3"

    # 1) 归集三件套（网盘版：未压缩定稿 MP4 + 整视频 MP3 + PDF）
    items = []
    mp4_src = target_mp4 if target_mp4.exists() else final
    if mp4_src.exists():
        items.append((mp4_src, bundle / f"{no}.{zh}.mp4"))
    for i, p in enumerate(pdfs):
        items.append((p, bundle / f"{no}.{zh}{'_' + str(i + 1) if i else ''}.pdf"))
    if mp3.exists():
        items.append((mp3, bundle / f"{no}.{zh}.mp3"))
    for src, dst in items:
        if src.resolve() != dst.resolve() and (not dst.exists()
                                               or dst.stat().st_size != src.stat().st_size):
            shutil.copy2(src, dst)
    root = cfg["netdisk_root"]
    lines = [f"第 {no} 课 {zh} · 上传清单", f"生成时间: {pecore.now()}",
             f"夸克目标: /{root}/{no}.{zh}/",
             f"百度目标: /apps/bdpan/{root}/{no}.{zh}/", "",
             "双轨交付：HTML 用 720p crf30 压缩视频 + Opus/ogg 分段音频；"
             "网盘用未压缩定稿 MP4（带双语字幕+片尾）+ 整视频 MP3 + PDF",
             "", "三件套（网盘版）："]
    for src, dst in items:
        lines.append(f"  OK  {dst.name:<38} {dst.stat().st_size/1048576:6.2f} MB  <- {src}")
    for label, suffix in (("MP4", ".mp4"), ("PDF", ".pdf"), ("MP3", ".mp3")):
        if not any(dst.suffix == suffix for _, dst in items):
            lines.append(f"  MISSING  {label} 未生成")

    # 2) 交付到定稿目录（用户指定：<DELIVERY_DIR>）
    lines += ["", f"定稿交付目录: {delivery}"]
    if target_mp4.exists():
        lines.append(f"  SKIP {target_mp4.name} 已存在 "
                     f"{target_mp4.stat().st_size/1048576:.1f} MB（人工定稿优先，不覆盖）")
    elif not args.apply:
        lines.append(f"  DRY  {target_mp4.name} <- final.mp4（--apply 才写入）")
    else:
        if not final.exists():
            raise pecore.PipelineError(f"缺 {final}，无法交付定稿 MP4")
        delivery.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final, target_mp4)
        lines.append(f"  OK   {target_mp4.name} 已写入 "
                     f"{target_mp4.stat().st_size/1048576:.1f} MB")

    # 3) 造脚本镜像，避免把产物塞进旧项目（upload_lesson.py 只认 <project>/tools/series.json）
    mirror = bundle / "mirror"
    slug = lesson.get("slug", f"{no}-lesson")
    m_tools = mirror / "tools"
    m_audio = mirror / "outputs" / "亲子英语" / slug / "audio"
    m_pdf = mirror / "outputs" / "亲子英语" / "全套PDF"
    for p in (m_tools, m_audio, m_pdf):
        p.mkdir(parents=True, exist_ok=True)
    (m_tools / "series.json").write_text(
        json.dumps({"lessons": [{"n": no, "slug": slug, "zh": zh}]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    if mp3.exists():
        shutil.copy2(mp3, m_audio / "full.mp3")
    for i, p in enumerate(pdfs):
        shutil.copy2(p, m_pdf / f"{no}.{zh}{'_' + str(i + 1) if i else ''}.pdf")
    lines += ["", "脚本镜像（不碰旧项目）:", f"  {mirror}",
              "  tools/series.json + outputs/亲子英语/<slug>/audio/full.mp3 + 全套PDF/", "",
              "上传：upload_lesson.py 一条命令双传夸克 + 百度（百度走本机 bdpan.exe CLI）",
              "注意：远端未做自动回读，请在 verify 报告里人工核对文件数与大小。"]
    (bundle / "manifest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    script = Path(cfg.get("quark_upload_script", ""))
    cmd_txt = f'python "{script}" --no {no} --project "{mirror}" --apply'
    if not args.apply:
        finish(cfg, d, lesson, "upload", "done", f"dry-run：{len(items)} 个文件已归集，镜像就绪")
        emit(f"清单: {bundle / 'manifest.txt'}")
        emit(f"真传（双网盘）时执行：{cmd_txt}")
        emit("（或 `pe.py upload <no> --apply`）")
        return 0

    if not script.exists():
        finish(cfg, d, lesson, "upload", "failed", "上传脚本不存在")
        raise pecore.PipelineError(f"请核对 config.yaml: quark_upload_script={script}")
    if not target_mp4.exists():
        finish(cfg, d, lesson, "upload", "failed", "定稿 MP4 未就位")
        raise pecore.PipelineError(f"定稿目录缺 {target_mp4}")
    if not Path(cfg.get("bdpan_exe", "")).exists():
        emit("[WARN] 找不到 bdpan.exe，百度侧可能被跳过")
    if not mp3.exists() or not pdfs:
        emit("[WARN] full.mp3 或 PDF 缺失，脚本会 WARN 跳过；成功证据可能不足 3 类")
    emit(f"[RUN] {cmd_txt}")
    cp = pecore.run([sys.executable, str(script), "--no", str(no),
                     "--project", str(mirror), "--apply"], timeout=3600)
    out = (cp.stdout or "") + "\n" + (cp.stderr or "")
    (bundle / "upload_log.txt").write_text(out, encoding="utf-8")
    try:
        warns = pecore.normalize_external_result(cp, out)
        for w in warns:
            emit(f"  [忽略·百度假FAIL] {w.strip()[:140]}")
        s = pecore.summarize_upload(out)
        if s["quark"] < 3 or s["baidu"] < 3:
            raise pecore.PipelineError(
                f"双网盘成功证据不足：夸克 {s['quark']}/3，百度 {s['baidu']}/3。\n"
                "  百度若为 `FAIL [百度]` 但日志里有 `✓ 已新建上传 (fsid …)`，属已知假 FAIL，"
                "可到网页端确认后重跑（大小一致会自动 SKIP）。\n"
                f"  完整日志: {bundle / 'upload_log.txt'}\n{out.strip()[-900:]}")
    except pecore.PipelineError as e:
        finish(cfg, d, lesson, "upload", "failed", "双网盘上传未确认成功")
        raise e
    finish(cfg, d, lesson, "upload", "done",
           f"夸克 {s['quark']}/3 + 百度 {s['baidu']}/3；定稿 {target_mp4.name}")
    return 0


def cmd_verify(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    lines = [f"# 终验报告 · 第 {lesson['no']} 课 {lesson.get('zh','')}", "",
             f"- 生成时间：{pecore.now()}", f"- 档案：`{d}`",
             f"- HTML 发布地址：{cfg.get('shared_site_index', '(未配置)')}", "",
             "## 产物", "", "| 阶段 | 产物 | 大小 |", "|---|---|---|"]
    problems: list[str] = []
    for s in pecore.STAGES:
        found, missing = pecore.check_expected(s, d)
        for label, rels in found.items():
            for rel in rels:
                p = d / rel
                size = f"{p.stat().st_size/1048576:.2f} MB" if p.stat().st_size > 1024**2 else f"{p.stat().st_size/1024:.0f} KB"
                lines.append(f"| {s} | {rel} | {size} |")
        # upload 的清单由下面单独判定，避免同一问题被计两次
        if s in ("new", "qa", "verify", "publish", "upload"):
            continue
        for m in missing:
            problems.append(f"[{s}] 缺 {m}")
    vp = pecore.probe_duration(d / "final.mp4") if (d / "final.mp4").exists() else None
    cp_ = pecore.probe_duration(d / "cut.mp4") if (d / "cut.mp4").exists() else None
    if vp and cp_:
        lines += ["", f"## 时长", "", f"- 剪辑 {cp_:.2f}s → 成片 {vp:.2f}s "
                  f"(差 {vp-cp_:.2f}s，目标 {cfg['outro_duration']}s)"]
    probs, notes = html_check(d)
    problems += [f"[html] {p}" for p in probs]
    lines += ["", "## HTML 体检", ""] + [f"- {n}" for n in notes] + [f"- 问题：{p}" for p in probs]

    # 来源标注：用户明确要求每课 HTML 都要写，终验必须查
    by = lesson.get("by") or ""
    lines += ["", "## 来源标注（必填）", ""]
    if not by:
        problems.append("[来源] lesson.json 的 by 为空 —— `pe.py source <no> --url <链接>` 可自动采集")
        lines.append("- 未登记来源")
    else:
        lines += [f"- 频道：YouTube {by}",
                  f"- 原视频：{lesson.get('source_url') or '-'}",
                  f"- 原标题：{lesson.get('source_title') or '-'}"]
        hp = d / "html" / "index.html"
        if hp.exists():
            ht = hp.read_text(encoding="utf-8", errors="replace")
            key = by.lstrip("@").lower()
            if "来源" not in ht or (key and key not in ht.lower()):
                problems.append(f"[来源] HTML 里未见「来源：YouTube {by}」—— "
                                "页头 srcbar 与页脚版权声明都要写")
                lines.append("- ⚠ HTML 未检测到来源标注")
            else:
                lines.append("- HTML 已含来源标注")
    man = d / "upload_bundle" / "manifest.txt"
    if man.exists():
        txt = man.read_text(encoding="utf-8")
        if "MISSING" in txt:
            problems.append("[upload] 上传清单里仍有 MISSING 项")
        lines += ["", "## 上传包", "", f"- `{man.relative_to(d)}`"]
    else:
        problems.append("[upload] 尚无上传清单")
    lines += ["", "## 人工核对（报告不替代）", "",
              "1. 打开 HTML 看手机端排版、音频能否播、Part 1–7 跳转是否正确。",
              "2. 打开 PDF 看有没有断页/乱码/内容截断。",
              "3. 到夸克 / 百度网盘确认 3 个文件都在、大小与本地一致（**远端未自动回读**）。",
              "4. 对照 `xhs.txt` 逐字比对英文原句与视频原文。",
              f"5. 确认页头写了 `来源：YouTube {by or '@频道'}`、页脚写了版权声明（用户明确要求）。",
              "6. 确认 HTML 站里是压缩视频/Opus 音频，网盘里是未压缩定稿 MP4 + 整视频 MP3（别混用）。", "",
              f"**CONCLUSION: {'PASS' if not problems else 'FAIL'}（{len(problems)} 项）**"]
    if problems:
        lines += [""] + [f"- {p}" for p in problems]
    lines += ["", "> 通过后 `pe.py approve <no> --stage final`，publish 才会解锁。"]
    (d / "reports").mkdir(parents=True, exist_ok=True)
    (d / "reports" / "verify_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    state = "done" if not problems else "failed"
    finish(cfg, d, lesson, "verify", state,
           f"{'PASS' if not problems else 'FAIL'}（{len(problems)} 项）")
    emit(f"报告: {d / 'reports' / 'verify_report.md'}")
    if problems:
        for p in problems:
            emit(f"  - {p}")
        emit("终验未通过：approve --stage final 会被拒绝，修完请重跑 verify。")
    return 0


SENSITIVE = ["私信我", "私我", "DM", "戳我", "加我", "加V", "加微信", "公众号",
             "发你资料", "领取资料包", "免费送", "资料包", "课件", "电子版",
             "0元", "免费", "白嫖", "福利", "限时", "秒杀", "下单", "购买链接",
             "包教包会", "保证", "一定学会", "必看"]


def cmd_publish(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    pecore.gate(lesson, "final", "publish")
    txt = d / "xhs.txt"
    if not txt.exists():
        raise pecore.PipelineError(f"缺 {txt}，先跑 build")
    body = txt.read_text(encoding="utf-8", errors="replace")
    hits = [w for w in SENSITIVE if w in body]
    lines = [f"第 {lesson['no']} 课 {lesson.get('zh','')} · 发布清单",
             f"生成时间: {pecore.now()}", "",
             f"视频: {d / 'final.mp4'}", f"文案: {txt}", "",
             "发帖前自检：",
             "  [ ] 标题 <=20 字、3 个备选风格不同",
             "  [ ] 8 句英文与视频原文逐字一致",
             "  [ ] 点评里提到的词确实出现在选句中",
             "  [ ] Hook 与本条视频内容相关、且风格不同于上一条",
             "  [ ] 3 条置顶评论都含「茴【关键词】」",
             "  [ ] 全文无平台敏感词" + (f"  ← ⚠ 命中: {', '.join(hits)}" if hits else "  (自动扫描通过)"),
             "", "—— 以下为文案原文，复制到小红书 / 抖音 ——", "", body]
    (d / "publish_checklist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    finish(cfg, d, lesson, "publish", "done",
           "清单已生成（不自动发帖）" + (f"；敏感词命中 {len(hits)} 个" if hits else ""))
    emit(f"清单: {d / 'publish_checklist.txt'}")
    return 0


def cmd_status(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    if args.json:
        emit(json.dumps({"dir": str(d), "lesson": lesson}, ensure_ascii=False, indent=2))
    else:
        emit("\n".join(status_lines(cfg, d, lesson)))
    return 0


def cmd_mark(args, cfg):
    d, lesson = open_lesson(cfg, args.no)
    stage = args.stage
    state = "done" if args.done else "pending"
    note = "手工登记"
    if state == "done" and not args.accept_missing:
        _, missing = pecore.check_expected(stage, d)
        if missing:
            raise pecore.PipelineError(
                f"拒绝标记 done：{stage} 的期望产物仍缺 {len(missing)} 项 -> {', '.join(missing)}\n"
                "产物确实在别处时，用 --accept-missing 显式登记（会写进备注）。")
    if args.accept_missing:
        note += "（已显式接受产物缺失）"
    finish(cfg, d, lesson, stage, state, note)
    return 0


# --------------------------------------------------------------------------- main
def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="覆盖 project_root")
    common.add_argument("--force", action="store_true", help="强制重跑本步")
    common.add_argument("--json", action="store_true", help="status 输出 JSON")
    p = argparse.ArgumentParser(prog="pe.py", description=f"{BANNER} 单课编排器")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name: str, *extra):
        sp = sub.add_parser(name, parents=[common])
        sp.add_argument("no", help="课号")
        for flags, kw in extra:
            sp.add_argument(*flags, **kw)
        return sp

    add("new", (["--zh"], {"required": True}), (["--en"], {"default": ""}),
        (["--by"], {"default": ""}), (["--cat"], {"default": ""}),
        (["--age"], {"default": "3-6 岁"}), (["--diff"], {"type": int, "default": 2}),
        (["--slug"], {"default": ""}), (["--url"], {"default": ""}))
    add("fetch", (["--url"], {"default": ""}))
    add("source", (["--url"], {"default": ""}), (["--by"], {"default": ""}))
    add("cut", (["--suggest"], {"action": "store_true"}),
        (["--keep"], {"nargs": 2, "metavar": ("START", "END")}))
    add("subs")
    add("qa")
    add("approve", (["--stage"], {"required": True, "choices": ["subs", "final"]}))
    add("build")
    add("upload", (["--apply"], {"action": "store_true"}))
    add("verify")
    add("publish")
    add("status")
    sp = add("mark", (["stage"], {"choices": pecore.STAGES}),
             (["--done"], {"action": "store_true"}),
             (["--pending"], {"action": "store_true"}),
             (["--accept-missing"], {"action": "store_true"}))
    return p


def main() -> int:
    args = build_parser().parse_args()
    try:
        cfg = pecore.load_config(args.root)
        fn = {
            "new": cmd_new, "fetch": cmd_fetch, "source": cmd_source,
            "cut": cmd_cut, "subs": cmd_subs,
            "qa": cmd_qa, "approve": cmd_approve, "build": cmd_build,
            "upload": cmd_upload, "verify": cmd_verify, "publish": cmd_publish,
            "status": cmd_status, "mark": cmd_mark,
        }[args.cmd]
        return fn(args, cfg)
    except pecore.PipelineError as e:
        emit(f"\n[ERROR] {e}")
        return 1
    except KeyboardInterrupt:
        emit("\n[中断]")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
