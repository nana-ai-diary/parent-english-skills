# -*- coding: utf-8 -*-
"""给每课生成**词级时间戳** work_prep/NN/words.json。

为什么需要
----------
`cutfit.py` 要回答「本段最后一个词是什么时候说完的」。原先只能靠
`transcript.json` 的**段级**时间在段内按词数均分插值 —— 段长 4~5 秒时
误差可达 0.3 秒，切点还是不够准。这里直接用 whisper 的
`word_timestamps=True` 拿每个词自己的起止时间。

产出: work_prep/NN/words.json = [{start, end, word}, …]

用法:
  python tools/wordtime.py            # 所有有 audio.wav 的课（已存在则跳过）
  python tools/wordtime.py 03 05      # 指定课
  python tools/wordtime.py --force    # 重算
"""
import io, json, os, re, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREP = os.path.join(ROOT, "work_prep")
NER = re.compile(r"\[[^\]]*\]|\([^)]*\)")

_m = None


def model():
    global _m
    if _m is None:
        from faster_whisper import WhisperModel
        _m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
    return _m


def one(n, force=False):
    wav = os.path.join(PREP, n, "audio.wav")
    dst = os.path.join(PREP, n, "words.json")
    if not os.path.isfile(wav):
        return "无 audio.wav"
    if os.path.isfile(dst) and not force:
        return "已存在"
    t0 = time.time()
    segs, info = model().transcribe(wav, beam_size=1, temperature=0,
                                    condition_on_previous_text=False,
                                    vad_filter=True, word_timestamps=True,
                                    language="en")
    rows = []
    for s in segs:
        for w in (s.words or []):
            t = NER.sub("", w.word).strip()
            if t:
                rows.append({"start": round(float(w.start), 3),
                             "end": round(float(w.end), 3), "word": t})
    io.open(dst, "w", encoding="utf-8").write(json.dumps(rows, ensure_ascii=False))
    return "%d 词 / %.1fs / 耗时 %.0fs" % (len(rows), info.duration, time.time() - t0)


def main():
    argv = sys.argv[1:]
    force = "--force" in argv
    picks = [a for a in argv if not a.startswith("--")]
    ns = picks or sorted(d for d in os.listdir(PREP) if os.path.isdir(os.path.join(PREP, d)))
    for n in ns:
        print("%-4s %s" % (n, one(n, force)), flush=True)


if __name__ == "__main__":
    main()
