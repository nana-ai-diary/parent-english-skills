# -*- coding: utf-8 -*-
"""体检某一课的  是否被 VAD 滤残，并可选重算。

用法:
  python tools/vadcheck.py 17 19 20 21 23         # 只报告，不写文件
  python tools/vadcheck.py 17 19 20 21 23 --write # 用覆盖率最高的那套参数写 words.json
"""
import io, json, os, re, sys, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import cutfit                                            # noqa: E402

ROOT = cutfit.ROOT
TAG = re.compile(r"<[^>]+>")
_m = None


def model():
    global _m
    if _m is None:
        from faster_whisper import WhisperModel
        _m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    return _m


SETS = [
    ("A 当前默认 VAD", dict(vad_filter=True)),
    ("C 关 VAD", dict(vad_filter=False, no_speech_threshold=0.6, log_prob_threshold=-1.0)),
]


def words_of(n, wav, kw):
    segs, _info = model().transcribe(wav, beam_size=1, temperature=0,
                                     condition_on_previous_text=False,
                                     language="en", word_timestamps=True, **kw)
    out = []
    for s in segs:
        for w in (s.words or []):
            t = cutfit.NER.sub("", w.word).strip()
            if t:
                out.append({"start": round(float(w.start), 3),
                            "end": round(float(w.end), 3), "word": t})
    return out


def coverage(n, rows):
    p = os.path.join(ROOT, "tools", "lessons")
    f = next(x for x in os.listdir(p) if x[:2] == n)
    d = json.load(io.open(os.path.join(p, f), encoding="utf-8"))
    texts = [TAG.sub("", b["en"]).strip() for b in d["part2"] if b.get("type") != "day"]
    A = [cutfit.key(w) for t in texts for w in t.split()]
    pr = cutfit.align(A, [cutfit.key(r["word"]) for r in rows])
    hit = set(i for i, _ in pr)
    return len(A), len(hit)


def main():
    argv = list(sys.argv[1:])
    write = "--write" in argv
    for n in [a for a in argv if not a.startswith("--")]:
        wav = os.path.join(ROOT, "work_prep", n, "audio.wav")
        print("=" * 70)
        print("第 %s 课   audio %.1fs" % (n, os.path.getsize(wav) / 32000.0))
        best = (None, -1, None)
        for tag, kw in SETS:
            t0 = time.time()
            rows = words_of(n, wav, kw)
            na, nh = coverage(n, rows)
            print("  %-16s 词 %4d   对齐覆盖 %3d/%-3d = %3.0f%%   %.0fs"
                  % (tag, len(rows), nh, na, 100.0 * nh / max(na, 1), time.time() - t0))
            if nh > best[1]:
                best = (tag, nh, rows)
        if write and best[0]:
            dst = os.path.join(ROOT, "work_prep", n, "words.json")
            io.open(dst, "w", encoding="utf-8").write(json.dumps(best[2], ensure_ascii=False))
            print("  已写入 words.json（取「%s」，%d 词）" % (best[0], len(best[2])))


if __name__ == "__main__":
    main()
