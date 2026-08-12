#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EyeHeist orchestrator: vyrenderuje N puzzle videi do output/ + .txt meta sidecar
(title/desc/hashtagy) -> nahratie riesi existujuci push_to_youtube.py (sloty 8/15/20).
Seedy sa loguju do used_puzzles.json (ziadne opakovanie kombinacii).

  python puzzle_daily.py 3
"""
import json, os, sys, time

import puzzle_engine as pe

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
USED = os.path.join(ROOT, "used_puzzles.json")

TITLES = [
    "Only 1% Spot It In 5 Seconds (Eye Test)",
    "Can You Beat Both Rounds? 99% Fail",
    "This 5-Second Eye Test Fools Everyone",
    "Find It Before The Timer Runs Out",
    "2 Puzzles. 5 Seconds Each. Ready?",
    "Your Eyes Are Elite If You Spot This",
    "99% Fail Round 2 Of This Test",
    "How Fast Can You Spot It?",
]
DESC = ("Two rounds, five seconds each - comment your score!\n"
        "Round 1 tests your eyes, round 2 tests your brain.\n"
        "Follow for a new test every day.\n\n"
        "#eyetest #puzzle #iqtest #brainteaser #riddle #quiz #challenge #shorts #fyp")


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3
    os.makedirs(OUT, exist_ok=True)
    used = json.load(open(USED, encoding="utf-8")) if os.path.exists(USED) else []
    seen = {u.get("seed") for u in used}
    day = time.strftime("%Y%m%d")
    made = 0
    seed = int(time.time()) % 100000
    while made < n:
        seed += 1
        if seed in seen:
            continue
        name = f"eyeheist_{day}_{made+1}"
        mp4 = os.path.join(OUT, name + ".mp4")
        try:
            info = pe.build_video(seed, mp4)
        except Exception as e:
            print(f"[CHYBA] render seed {seed}: {str(e)[:160]}")
            continue
        title = TITLES[(seed + made) % len(TITLES)]
        with open(os.path.join(OUT, name + ".txt"), "w", encoding="utf-8") as f:
            f.write(title + "\n\n" + DESC + "\n\nMusic: " + (info.get("music") or "") +
                    " - Kevin MacLeod (incompetech.com), CC BY 4.0\n")
        used.append({"seed": seed, "date": day, "file": name + ".mp4", "len": round(info["total"], 1)})
        seen.add(seed); made += 1
        print(f"  OK {name}.mp4 ({info['total']:.1f}s, seed {seed})")
    json.dump(used[-500:], open(USED, "w", encoding="utf-8"), indent=1)
    print(f"HOTOVO: {made}/{n} videi.")


if __name__ == "__main__":
    main()
