#!/usr/bin/env python3
"""
视频/音频转文字（faster-whisper）
用法: python transcribe.py <video_path> [model_size]
  model_size: tiny/base/small/medium/large-v3，默认 base
输出: JSON { text, segments[{start, end, text}], language }
"""
import sys
import os
import json
import ssl
import urllib.request
from pathlib import Path


def ensure_model(model_size: str) -> str:
    """确保 faster-whisper 模型已下载，失败时自动手动下载。"""
    cache_dir = Path.home() / f".cache/whisper_{model_size}_ct2"
    if cache_dir.exists() and any(cache_dir.iterdir()):
        return str(cache_dir)

    # 尝试正常下载
    try:
        from faster_whisper import WhisperModel
        WhisperModel(model_size, device="cpu", compute_type="int8",
                     download_root=str(Path.home() / ".cache"))
        return str(cache_dir)
    except Exception:
        pass

    # 手动下载（绕过 SSL 问题）
    print(f"[transcribe] 模型未找到，正在手动下载 {model_size} ...", file=sys.stderr)
    cache_dir.mkdir(parents=True, exist_ok=True)

    base_url = f"https://huggingface.co/Systran/faster-whisper-{model_size}/resolve/main/"
    files = [
        "config.json", "model.bin", "tokenizer.json",
        "vocabulary.txt", "vocabulary.json",
        "preprocessor_config.json",
    ]
    # 安全加固（安装时修改）：原脚本此处关闭了 TLS 证书校验
    # （check_hostname=False / verify_mode=CERT_NONE），
    # 会导致模型权重可被中间人替换。现改为使用默认的安全上下文。
    ctx = ssl.create_default_context()

    for fname in files:
        dest = cache_dir / fname
        if dest.exists():
            continue
        url = base_url + fname
        try:
            urllib.request.urlretrieve(url, str(dest), context=ctx)
            print(f"  ✓ {fname}", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ {fname} 下载失败: {e}", file=sys.stderr)

    return str(cache_dir)


def transcribe(video_path: str, model_size: str = "base") -> dict:
    from faster_whisper import WhisperModel

    model_dir = ensure_model(model_size)
    model = WhisperModel(model_dir, device="cpu", compute_type="int8")

    segments_gen, info = model.transcribe(
        video_path,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    segments = []
    full_text_parts = []
    for seg in segments_gen:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        full_text_parts.append(seg.text.strip())

    return {
        "text": " ".join(full_text_parts),
        "segments": segments,
        "language": getattr(info, "language", "unknown"),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python transcribe.py <video_path> [model_size]")
        sys.exit(1)

    video_path = sys.argv[1]
    model_size = sys.argv[2] if len(sys.argv) > 2 else "base"

    if not os.path.exists(video_path):
        print(f"错误: 文件不存在 {video_path}", file=sys.stderr)
        sys.exit(1)

    result = transcribe(video_path, model_size)
    print(json.dumps(result, ensure_ascii=False, indent=2))
