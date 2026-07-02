#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doplni banku 'specov' (filozoficky text na obrazovku + caption + nahodna simulacia) cez
GitHub Models (zadarmo). Nika: hypnoticke fyzikalne/chaos simulacie (Entropy)."""
import json, os, random, re, sys
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "topics_bank.json")
STATE = os.path.join(ROOT, "used_topics.json")
# vizualne ODLISNE, OVERENE simulacie (kazda iny tvar: gula / motyl / orb+vir / spirala)
SIMS = ["stream_sphere", "lorenz_swarm", "aizawa_attractor", "halvorsen_attractor",
        "rossler_attractor", "double_pendulum", "clifford_morph", "galaxy_spiral", "flow_field"]
SCHEMES = ["cool_warm", "ember", "ice", "neon", "aurora", "sunset"]   # farebne variacie -> ani rovnaka sim nevyzera rovnako

TARGET = int(os.environ.get("TOPICS_TARGET", "15"))
MODEL = os.environ.get("MODELS_MODEL", "openai/gpt-4o-mini")
BASE = os.environ.get("MODELS_BASE_URL", "https://models.github.ai/inference")
TOKEN = os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")

SYSTEM = ("You write short, punchy, mind-bending one-liners about order, chaos, entropy, physics and "
          "the universe for a viral science-simulation brand called Entropy (mesmerizing particle "
          "simulations on black). Profound but dead simple. You output strict JSON, nothing else.")

EXAMPLE = {
    "onscreen": "Order is just chaos waiting to happen.",
    "title": "Order Is Just Chaos Waiting to Happen",
    "description": "5000 particles fall into a sphere and bounce into beautiful chaos. Like + comment if you want part 2.",
    "hashtags": ["#science", "#physics", "#chaos", "#simulation", "#oddlysatisfying", "#shorts", "#fyp"],
}


def build_prompt(n, existing):
    return (
        f"Generate {n} NEW items for a viral physics/chaos SIMULATION brand 'Entropy' "
        "(mesmerizing glowing particle simulations on black, no voiceover).\n"
        "Return ONLY a JSON array (no markdown). Each item EXACTLY this schema:\n"
        f"{json.dumps(EXAMPLE, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- onscreen: ONE short, profound, mind-bending line (MAX 7 words) about order / chaos / entropy / "
        "physics / the universe, shown ON the video. Simple, punchy, scroll-stopping. "
        "e.g. 'Order is just chaos waiting to happen', 'Everything tends toward chaos', "
        "'Chaos always hides perfect order', 'Even stars obey simple rules'.\n"
        "- title: the onscreen line written as a YouTube title (Title Case).\n"
        "- description: ONE intriguing sentence about a mesmerizing particle simulation, then an "
        "engagement hook like 'Like + comment if you want part 2.'\n"
        "- About half the time add ONE fitting emoji at the very END of the description (e.g. 🌀, ⚛️, 🔭, ✨). "
        "Emoji ONLY in description, NEVER in onscreen/title.\n"
        "- hashtags: 6-8 tags including #science #simulation #oddlysatisfying #shorts #fyp.\n"
        "- Accurate, awe-inspiring, never pseudoscience.\n"
        f"- Do NOT reuse any of these existing lines: {existing}\n"
        "Return ONLY the JSON array."
    )


def call_model(text):
    r = requests.post(BASE.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                      json={"model": MODEL, "temperature": 0.98,
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": text}]}, timeout=180)
    if r.status_code >= 400:
        raise RuntimeError(f"Models API {r.status_code}: {r.text[:400]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_json(s):
    s = re.sub(r"^```(?:json)?", "", s.strip()).strip()
    s = re.sub(r"```$", "", s).strip()
    a, b = s.find("["), s.rfind("]")
    return json.loads(s[a:b + 1] if a != -1 and b != -1 else s)


def valid(t):
    if not isinstance(t, dict) or "onscreen" not in t:
        return False
    t.setdefault("title", t["onscreen"])
    t.setdefault("description", t["onscreen"] + " Like + comment if you want part 2.")
    t.setdefault("hashtags", ["#science", "#simulation", "#oddlysatisfying", "#shorts", "#fyp"])
    return bool(str(t["onscreen"]).strip())


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN"); sys.exit(1)
    bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else []
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    seen = {t["onscreen"] for t in bank}
    unused = [t for t in bank if t["onscreen"] not in used]
    need = TARGET - len(unused)
    added = 0
    if need > 0:
        print(f"Generujem ~{need} novych cez {MODEL}...")
        for t in extract_json(call_model(build_prompt(need + 3, sorted(seen)))):
            if valid(t) and t["onscreen"] not in seen:
                t["seed"] = random.randint(1, 99999)
                bank.append(t); seen.add(t["onscreen"]); added += 1
    else:
        print(f"Banka OK: {len(unused)} nepouzitych (len premiesam simulacie).")
    rebalance(bank, set(used))                        # vzdy: rozhod sim tak, aby sa NEopakovali za sebou
    json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Pridanych {added}. Banka ma {len(bank)}. Simulacie premiesane (ziadne 2 rovnake za sebou).")


def rebalance(bank, used):
    """Priradi NEPOUZITYM specom simulacie po kruhu (ziadne 2 rovnake za sebou) + nahodnu schemu.
    Pouzite (uz publikovane) ostavaju nezmenene."""
    order = SIMS[:]; random.shuffle(order)
    i, prev = 0, None
    for t in bank:
        if t.get("onscreen") in used:
            prev = t.get("sim"); continue
        sim = order[i % len(order)]
        if sim == prev and len(order) > 1:
            i += 1; sim = order[i % len(order)]
        t["sim"] = sim
        t["scheme"] = random.choice(SCHEMES)
        t.setdefault("seed", random.randint(1, 99999))
        prev = sim; i += 1


if __name__ == "__main__":
    main()
