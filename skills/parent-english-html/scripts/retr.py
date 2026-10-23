import sys
from faster_whisper import WhisperModel

PROMPT = {
    "19": "playground safety do not run stop wait your turn hold my hand slide monkey bars swings get hurt be careful watch out",
    "20": "playground safety slide never climb up the slide sit down feet first wait your turn take turns be careful watch out hold on",
    "21": "playground rides names swing slide merry-go-round seesaw sandbox monkey bars climbing frame spring rider",
    "23": "car seat safety buckle up sit up straight seat belt window hands to yourself grandma school late",
    "25": "bus safety rules watch your step sit down no standing never distract the driver no toys allowed no food allowed be respectful trash bin",
    "27": "taking off clothes help your child take off sweater socks shirt shorts pull it off arm head out heel push down very good",
}

n = sys.argv[1]
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, info = m.transcribe(
    "work_prep/%s/audio.wav" % n,
    beam_size=1, temperature=0,
    condition_on_previous_text=False,
    initial_prompt=PROMPT.get(n, ""),
)
out = [(s.start, s.end, s.text.strip()) for s in segs]
print("n=%d speech=%.1f/%.1f" % (len(out), sum(b - a for a, b, _ in out), info.duration))
for a, b, t in out:
    print("%7.2f %7.2f  %s" % (a, b, t))
