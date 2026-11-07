# -*- coding: utf-8 -*-
"""pecore.py - parent-english-pipeline 的契约层：配置、路径、状态读写、进程调用。

设计原则：不假成功。任何一步的产物检查都走 expected()，任何子进程失败都归一化成
PipelineError，调用方必须显式处理。
"""
from __future__ import annotations

import datetime as _dt
import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.yaml"

STAGES = ["new", "fetch", "cut", "subs", "qa", "build", "upload", "verify", "publish"]
STAGE_LABEL = {
    "new": "建档", "fetch": "找素材/下载", "cut": "剪辑2分钟", "subs": "双语字幕",
    "qa": "字幕核对", "build": "HTML/MP3/PDF/文案", "upload": "网盘上传",
    "verify": "终验", "publish": "发帖",
}
STATE_RANK = {"pending": 0, "blocked": 1, "failed": 2, "skipped": 3, "done": 4}
VALID_STATES = set(STATE_RANK)


class PipelineError(Exception):
    """可被 CLI 捕获并转成退出码 1 的确定性错误。"""


def now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_config(root_override: str | None = None) -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if root_override:
        cfg["project_root"] = root_override
    cfg["project_root"] = str(cfg["project_root"]).replace("\\", "/").rstrip("/")
    for key in ("preset_video", "font_path", "python_venv", "legacy_project",
                "quark_upload_script"):
        if cfg.get(key):
            cfg[key] = str(cfg[key]).replace("\\", "/")
    # 默认把 python_venv 作为主解释器；外部 CLI 用当前解释器也能跑
    return cfg


def lessons_root(cfg: dict) -> Path:
    return Path(cfg["project_root"]) / "lessons"


def find_lesson_dir(cfg: dict, no: str | int) -> Path:
    root = lessons_root(cfg)
    key = str(no).strip()
    if key.isdigit():
        n = int(key)
        patterns = {f"{n}-*", f"{n:02d}-*"}
    else:
        patterns = {f"{key}-*"}
    hits = sorted({p for pat in patterns for p in root.glob(pat) if p.is_dir()},
                  key=lambda p: p.name)
    if not hits:
        raise PipelineError(f"找不到第 {no} 课的档案：{root} 下无匹配目录。先跑 `pe.py new {no} ...`")
    if len(hits) > 1:
        raise PipelineError(f"第 {no} 课有多个目录，请人工确认：{[p.name for p in hits]}")
    return hits[0]


def new_lesson(cfg: dict, no: int, zh: str, en: str = "", by: str = "",
               cat: str = "", age: str = "3-6 岁", diff: int = 2,
               slug: str = "", url: str = "") -> dict:
    return {
        "schema": 1,
        "no": int(no),
        "slug": slug or f"{int(no):02d}-lesson",
        "zh": zh, "en": en, "by": by, "source_url": url,
        "cat": cat, "age": age, "diff": diff,
        "cut": {"keep": None, "duration": None},
        "created": now(),
        "stages": {s: {"state": "pending", "ts": None, "note": ""} for s in STAGES},
        "approvals": {"subs": None, "final": None},
        "artifacts": {},
    }


def read_lesson(d: Path) -> dict:
    p = d / "lesson.json"
    if not p.exists():
        raise PipelineError(f"档案缺失：{p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def write_lesson(d: Path, lesson: dict) -> None:
    p = d / "lesson.json"
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(lesson, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def set_stage(lesson: dict, stage: str, state: str, note: str = "") -> None:
    if stage not in STAGES:
        raise PipelineError(f"未知阶段：{stage}")
    if state not in VALID_STATES:
        raise PipelineError(f"未知状态：{state}")
    lesson["stages"][stage] = {"state": state, "ts": now(), "note": note}


def stage_state(lesson: dict, stage: str) -> str:
    return lesson["stages"].get(stage, {}).get("state", "pending")


def approved(lesson: dict, stage: str) -> bool:
    v = lesson.get("approvals", {}).get(stage)
    return bool(v)


def expected(stage: str, d: Path) -> dict[str, str]:
    """每步的期望产物：label -> 相对路径（可含 * 通配符）。"""
    table = {
        "new": {"档案": "lesson.json"},
        "fetch": {"下载原件": "src.mp4"},
        "cut": {"剪辑成片": "cut.mp4"},
        "subs": {"词级转录": "transcript.json", "完整清单": "subtitle_manifest.csv",
                 "校对后双语": "subs.json", "带片尾成片": "final.mp4"},
        "qa": {"QA 报告": "reports/qa_report.md", "抽帧拼图": "reports/frames_sheet.jpg"},
        "build": {"HTML": "html/index.html", "整视频音频": "html/audio/full.mp3",
                  "PDF": "pdf/*.pdf", "文案": "xhs.txt"},
        "upload": {"上传清单": "upload_bundle/manifest.txt"},
        "verify": {"终验报告": "reports/verify_report.md"},
        "publish": {"发布清单": "publish_checklist.txt"},
    }
    return table.get(stage, {})


def check_expected(stage: str, d: Path) -> tuple[dict[str, list[str]], list[str]]:
    """返回 ({label: [匹配到的路径]}, [缺失 label])。"""
    found: dict[str, list[str]] = {}
    missing: list[str] = []
    for label, rel in expected(stage, d).items():
        matches = sorted(str(Path(p).relative_to(d)).replace("\\", "/")
                         for p in glob.glob(str(d / rel)) if Path(p).stat().st_size > 0)
        found[label] = matches
        if not matches:
            missing.append(f"{label} ({rel})")
    return found, missing


def scan_artifacts(d: Path) -> dict:
    out = {}
    for stage in STAGES:
        found, _ = check_expected(stage, d)
        out[stage] = {k: v for k, v in found.items() if v}
    return out


def tool(name: str) -> str:
    p = shutil.which(name)
    if not p:
        raise PipelineError(f"找不到命令：{name}")
    return p


def run(argv: list[str], *, cwd: str | Path | None = None, timeout: int = 1800,
        env_extra: dict | None = None, check: bool = False) -> subprocess.CompletedProcess:
    """跑子进程，始终返回 CompletedProcess；check=True 时非零退出抛 PipelineError。"""
    env = os.environ.copy()
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items() if v})
    try:
        cp = subprocess.run(argv, cwd=str(cwd) if cwd else None, env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout)
    except FileNotFoundError as e:
        raise PipelineError(f"命令不存在：{argv[0]} ({e})") from e
    except subprocess.TimeoutExpired as e:
        raise PipelineError(f"命令超时（{timeout}s）：{argv[0]}") from e
    if check and cp.returncode != 0:
        tail = (cp.stderr or cp.stdout or "").strip()[-800:]
        raise PipelineError(f"命令失败 rc={cp.returncode}: {' '.join(map(str, argv[:4]))}...\n{tail}")
    return cp


def probe_duration(path: str | Path) -> float:
    cp = run([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
              "-of", "default=nw=1:nk=1", str(path)])
    if cp.returncode != 0:
        raise PipelineError(f"ffprobe 读不出时长：{path}\n{cp.stderr.strip()}")
    try:
        return float((cp.stdout or "").strip().splitlines()[0])
    except (ValueError, IndexError) as e:
        raise PipelineError(f"ffprobe 时长非数字：{path} -> {cp.stdout!r}") from e


def normalize_external_result(cp: subprocess.CompletedProcess, text: str | None = None) -> list[str]:
    """把外部工具的错误归一化：退出码、isError、traceback、真 FAIL 都算失败。
    返回 warnings 列表（目前主要是百度的「假 FAIL」）。

    特殊情况（2026-11-06 第 48 课实测）：百度列表/回读 API 偶发 errno=-7，
    upload_lesson.py 会把**已成功上传**的文件打印成 `FAIL [百度] …`，
    但同一段输出里有 `✓ 已新建上传 (fsid …)` / `"status": "ok"`。
    这类行不算失败，只作为 warning 返回；夸克侧的 FAIL 仍是真失败。
    """
    blob = (text if text is not None else ((cp.stdout or "") + "\n" + (cp.stderr or "")))
    low = blob.lower()
    bad_markers = ['"iserror": true', '"iserror":true', "traceback (most recent",
                   "authentication failed", "401 unauthorized", "sign in to confirm"]
    if cp.returncode != 0:
        raise PipelineError(f"外部命令失败 rc={cp.returncode}\n{blob.strip()[-1200:]}")
    for m in bad_markers:
        if m in low:
            raise PipelineError(f"外部命令回报了错误标记 ({m})\n{blob.strip()[-1200:]}")
    success_evidence = any(k in blob for k in
                           ("已新建上传", "fsid", '"status": "ok"', "OK    [百度]"))
    fail_lines = [ln for ln in blob.splitlines()
                  if "fail" in ln.lower()
                  and "0 fail" not in ln.lower() and "fail: 0" not in ln.lower()]
    false_fails = [ln for ln in fail_lines if "[百度]" in ln and success_evidence]
    real_fails = [ln for ln in fail_lines if ln not in false_fails]
    if real_fails:
        raise PipelineError("外部命令输出含真实 FAIL：\n  " + "\n  ".join(real_fails[:6])
                            + f"\n{blob.strip()[-800:]}")
    return false_fails


def summarize_upload(out: str) -> dict:
    """按网盘分别统计成功证据，避免「只传了夸克」被当成全成功。"""
    lines = out.splitlines()
    quark = sum(1 for ln in lines
                if "[百度]" not in ln
                and re.match(r"\s*(OK|SKIP)\s+\[", ln))
    baidu = sum(1 for ln in lines
                if "[百度]" in ln
                and ("已新建上传" in ln or "fsid" in ln
                     or re.match(r"\s*(OK|SKIP)\s+\[百度\]", ln)))
    return {"quark": quark, "baidu": baidu}


SOURCE_KEYS = ("by", "source_url", "source_title", "source_video_id",
               "source_channel_id", "source_duration", "source_captured_at")


def parse_source_info(info: dict) -> dict:
    """从 yt-dlp 的 info.json 提取来源，映射成 parent-english-html 的 `by` 规范：
    有 @handle 就带 @（如 @babylist），没有就用频道显示名（如 Confucius Institute Adelaide）。
    """
    def pick(*keys: str) -> str:
        for k in keys:
            v = info.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""

    handle = ""
    for cand in (pick("uploader_id"), pick("uploader"), pick("channel"),
                 pick("channel_id")):
        if cand.startswith("@") and not cand.startswith("@UC"):
            handle = cand
            break
    by = handle or pick("channel", "uploader") or pick("uploader_id")
    vid = pick("id", "video_id")
    url = pick("webpage_url", "original_url") or (
        f"https://www.youtube.com/watch?v={vid}" if vid else "")
    return {
        "by": by,
        "source_url": url,
        "source_title": pick("title", "fulltitle"),
        "source_video_id": vid,
        "source_channel_id": pick("channel_id"),
        "source_duration": info.get("duration"),
        "source_captured_at": now(),
    }


def apply_source(lesson: dict, src: dict, *, overwrite: bool = False) -> list[str]:
    """把来源字段写进 lesson.json，返回变更说明。默认不覆盖已有的 by。"""
    changed = []
    for k in SOURCE_KEYS:
        v = src.get(k)
        if v in (None, ""):
            continue
        if k == "by" and lesson.get("by") and not overwrite:
            continue
        if lesson.get(k) != v:
            lesson[k] = v
            changed.append(f"{k}={v}")
    return changed


def ensure_dirs(d: Path) -> None:
    for sub in ("subtitle_work/txt", "subtitle_work/srt_only", "html/audio",
                "html/video", "html/img", "pdf", "reports", "upload_bundle"):
        (d / sub).mkdir(parents=True, exist_ok=True)


def gate(lesson: dict, required: str, action: str) -> None:
    if not approved(lesson, required):
        raise PipelineError(
            f"闸门未通过：{action} 需要人工确认 `{required}`。\n"
            f"  先跑 `pe.py qa {lesson['no']}`（或 verify），看完报告再 "
            f"`pe.py approve {lesson['no']} --stage {required}`")
