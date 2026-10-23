import json, sys, glob, os
sys.path.insert(0, "tools")
import build_lesson as B
targets = sys.argv[1:]
for f in sorted(glob.glob("tools/lessons/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    slug = d.get("slug")
    if targets and slug not in targets: continue
    print("\n" + "="*70)
    print("###", slug)
    cur = None
    for b in d.get("part2") or []:
        if b["type"] == "day":
            cur = b["id"]; print(f"\n-- {cur} --")
        else:
            print(f"  [{b.get('no')}] {B.plain(b.get('en',''))}")
