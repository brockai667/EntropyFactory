#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vyberie N nepouzitych specov z topics_bank.json, vyrenderuje kazdy cez make_video.py.
Stav v used_topics.json (kluc = 'onscreen' text) -> sim sa nikdy nezopakuje."""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "topics_bank.json")
STATE = os.path.join(ROOT, "used_topics.json")


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", (t or "").lower()).strip("_")[:50] or "sim"


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    bank = json.load(open(BANK, encoding="utf-8"))
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    remaining = [t for t in bank if t.get("onscreen") not in used]
    if not remaining:
        print("Vsetky specy pouzite. Pridaj nove (generate_topics.py)."); return
    batch = remaining[:n]
    os.makedirs(os.path.join(ROOT, "scripts"), exist_ok=True)
    made = 0
    for i, spec in enumerate(batch, 1):
        path = os.path.join(ROOT, "scripts", f"auto_{slug(spec.get('title') or spec['onscreen'])}.json")
        json.dump(spec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n===== [{i}/{len(batch)}] {spec.get('sim')} | {spec['onscreen']} =====")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "make_video.py"), path])
        if r.returncode == 0:
            made += 1; used.append(spec["onscreen"])
            json.dump(used, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        else:
            print(f"[CHYBA] render zlyhal: {spec['onscreen']}")
    print(f"\n========== HOTOVO: {made} videi ==========")


if __name__ == "__main__":
    main()
