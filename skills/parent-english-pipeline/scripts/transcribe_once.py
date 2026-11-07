# -*- coding: utf-8 -*-
"""transcribe_once.py - 全链路唯一一次转录，产物供字幕 / HTML / 文案共用。

固定规范：word_timestamps=True、vad_filter=False（VAD 会吞掉安静/短促台词）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from faster_whisper import WhisperModel


def main() -> int:
    src, out, model_name, compute = sys.argv[1:5]
    model = WhisperModel(model_name, device="cpu", compute_type=compute)
    kwargs = dict(
        language="en", word_timestamps=True, vad_filter=False,
        beam_size=1, temperature=0.0, condition_on_previous_text=False,
        no_speech_threshold=0.6, log_prob_threshold=-1.0,
    )
    try:
        segments, info = model.transcribe(src, **kwargs)
    except TypeError:
        segments, info = model.transcribe(
            src, language="en", word_timestamps=True, vad_filter=False,
            beam_size=1, temperature=0.0, condition_on_previous_text=False)
    data = {
        "source": str(src), "model": model_name,
        "language": getattr(info, "language", "en"),
        "duration": getattr(info, "duration", None),
        "segments": [],
    }
    for seg in segments:
        item = {"start": seg.start, "end": seg.end, "text": seg.text, "words": []}
        for w in (seg.words or []):
            item["words"].append({
                "word": w.word, "start": w.start, "end": w.end,
                "probability": getattr(w, "probability", None),
            })
        data["segments"].append(item)
        print(f"  {seg.start:7.2f} -> {seg.end:7.2f}  {seg.text.strip()[:70]}", flush=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(data['segments'])} segments -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
