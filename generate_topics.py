#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Doplni banku 'specov' (filozoficky text na obrazovku + caption + nahodna simulacia) cez
GitHub Models (zadarmo). Nika: hypnoticke fyzikalne/chaos simulacie (Entropy).
NIC sa nesmie OPAKOVAT ani byt PODOBNE: 3 vrstvy ochrany -> (1) semanticka dedup textov,
(2) rebalance simov: ziadny sim v poslednom okne + ziadna rovnaka RODINA za sebou + ina schema +
unikatny seed, (3) silny prompt na variabilitu temy."""
import json, os, random, re, sys
import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "topics_bank.json")
STATE = os.path.join(ROOT, "used_topics.json")
SIMS = ["stream_sphere", "weaving_pens", "spirograph", "harmonograph", "wander_ribbons", "lorenz_swarm",
        "aizawa_attractor", "halvorsen_attractor", "rossler_attractor", "double_pendulum",
        "clifford_morph", "galaxy_spiral", "flow_field"]
SCHEMES = ["cool_warm", "ember", "ice", "neon", "aurora", "sunset"]
# RODINY (podobny vzhlad) -> nedavaj 2 z rovnakej rodiny za sebou
FAMILY = {
    "weaving_pens": "pen", "spirograph": "pen", "harmonograph": "pen", "wander_ribbons": "pen",
    "lorenz_swarm": "attractor", "aizawa_attractor": "attractor", "thomas_attractor": "attractor",
    "halvorsen_attractor": "attractor", "rossler_attractor": "attractor",
    "stream_sphere": "particles", "particles_in_circle": "particles", "double_pendulum": "particles",
    "flow_field": "field", "galaxy_spiral": "field", "clifford_morph": "field",
}

TARGET = int(os.environ.get("TOPICS_TARGET", "15"))
MODEL = os.environ.get("MODELS_MODEL", "openai/gpt-4o-mini")
BASE = os.environ.get("MODELS_BASE_URL", "https://models.github.ai/inference")
TOKEN = os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")

SYSTEM = ("You write short, punchy, mind-bending one-liners for a viral science-simulation brand "
          "called Entropy (mesmerizing glowing simulations on black). Your theme is the whole world "
          "of order, chaos, entropy, emergence, patterns, symmetry, fractals, randomness, the butterfly "
          "effect, self-organization, feedback, waves, infinity and hidden structure. Every line is a "
          "GENUINELY DIFFERENT idea. Profound but dead simple. You output strict JSON, nothing else.")

EXAMPLE = {
    "onscreen": "Small causes, giant consequences.",
    "title": "Small Causes, Giant Consequences",
    "description": "Two nearly identical starts drift into totally different fates. Like + comment if you want part 2.",
    "hashtags": ["#science", "#physics", "#chaos", "#simulation", "#oddlysatisfying", "#shorts", "#fyp"],
}


def build_prompt(n, existing):
    return (
        f"Generate {n} NEW items for a viral physics/chaos SIMULATION brand 'Entropy' "
        "(mesmerizing glowing simulations on black, no voiceover).\n"
        "Return ONLY a JSON array (no markdown). Each item EXACTLY this schema:\n"
        f"{json.dumps(EXAMPLE, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- onscreen: ONE short, profound line (MAX 7 words) shown ON the video. Cover the WHOLE theme: "
        "order, chaos, entropy, emergence, patterns, symmetry, fractals, randomness, the butterfly effect, "
        "self-organization, feedback, waves, infinity, probability, hidden structure — NOT just 'order vs chaos'.\n"
        "- VARY THE ANGLE across the batch: mix statements, questions, paradoxes and surprising truths. "
        "e.g. 'Patterns hide in the noise', 'Where does order come from?', 'A shape made of pure math', "
        "'Randomness has a rhythm', 'Simple rules, endless forms', 'Nothing here is truly random'.\n"
        "- Each line must be a GENUINELY DIFFERENT idea. Do NOT repeat the same subject, word or concept "
        "as another line even reworded, and do NOT start more than one line with the same word "
        "(avoid overusing 'Order', 'Chaos', 'Entropy', 'Everything').\n"
        "- title: the onscreen line written as a YouTube title (Title Case).\n"
        "- description: ONE intriguing sentence about a mesmerizing simulation, then a hook like "
        "'Like + comment if you want part 2.'\n"
        "- About half the time add ONE fitting emoji at the very END of the description (e.g. 🌀, ⚛️, 🔭, ✨). "
        "Emoji ONLY in description, NEVER in onscreen/title.\n"
        "- hashtags: 6-8 tags including #science #simulation #oddlysatisfying #shorts #fyp.\n"
        "- Accurate, awe-inspiring, never pseudoscience.\n"
        f"- Do NOT reuse or paraphrase any of these existing lines: {existing}\n"
        "Return ONLY the JSON array."
    )


def call_model(text):
    r = requests.post(BASE.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                      json={"model": MODEL, "temperature": 1.0,
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


# ---- semanticka dedup: dve linky su 'podobne' ak zdielaju dost klucovych slov ----
_STOP = {"the", "is", "a", "of", "to", "and", "in", "on", "it", "its", "are", "that", "from", "into",
         "just", "always", "never", "every", "all", "only", "as", "or", "but", "so", "how", "why",
         "what", "when", "your", "you", "this", "these", "there", "they", "them", "for", "with", "not",
         "be", "do", "than", "even", "still", "true", "real", "can", "will", "has", "have", "we"}


def _sig(line):
    return set(w for w in re.findall(r"[a-z]+", str(line).lower()) if len(w) > 2 and w not in _STOP)


def _too_similar(sig, sigs):
    if not sig:
        return False
    for es in sigs:
        if not es:
            continue
        inter = len(sig & es)
        if inter >= 3 or (inter >= 2 and inter / (len(sig | es) or 1) >= 0.5):
            return True
    return False


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN"); sys.exit(1)
    bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else []
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    used_set = set(used)

    # (0) vycisti NEPOUZITE podobne linky z banky (publikovane necha) -> fronta nema klony
    cleaned, sigs, removed = [], [], 0
    for t in bank:
        line = t.get("onscreen", "")
        if line in used_set:
            cleaned.append(t); sigs.append(_sig(line)); continue      # publikovane -> nechaj
        s = _sig(line)
        if line and not _too_similar(s, sigs):
            cleaned.append(t); sigs.append(s)
        else:
            removed += 1
    bank = cleaned
    if removed:
        print(f"Odstranenych {removed} podobnych nepouzitych liniek z banky.")

    seen = {t["onscreen"] for t in bank}
    unused = [t for t in bank if t["onscreen"] not in used_set]
    need = TARGET - len(unused)
    added = 0
    if need > 0:
        print(f"Generujem ~{need} novych cez {MODEL}...")
        try:
            items = extract_json(call_model(build_prompt(need + 5, sorted(seen))))
        except Exception as e:
            print("generovanie zlyhalo:", str(e)[:120]); items = []
        for t in items:
            if not valid(t) or t["onscreen"] in seen:
                continue
            s = _sig(t["onscreen"])
            if _too_similar(s, sigs):                     # podobne existujucemu -> preskoc
                print("  preskocene (podobne):", t["onscreen"]); continue
            t["seed"] = random.randint(1, 99999)
            bank.append(t); seen.add(t["onscreen"]); sigs.append(s); added += 1
    else:
        print(f"Banka OK: {len(unused)} nepouzitych (len premiesam simulacie).")
    rebalance(bank, used_set)
    json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Pridanych {added}. Banka ma {len(bank)}. Sim/schema/seed premiesane (ziadne opakovanie ani podobne).")


def rebalance(bank, used):
    """Priradi NEPOUZITYM specom sim+schemu tak, aby sa NEOPAKOVALI ani NEBOLI PODOBNE:
    ziadny sim v poslednom okne (~5 videi), ziadna rovnaka RODINA za sebou (nie 2 pero-art/atraktory
    po sebe), ina schema nez predosla, unikatny seed. Publikovane ostavaju nezmenene."""
    seeds = {t.get("seed") for t in bank if t.get("seed")}
    recent, prev_fam, prev_scheme = [], None, None
    for t in bank:
        if t.get("onscreen") in used:                     # publikovane -> nechaj, zapocitaj do 'recent'
            s = t.get("sim")
            if s:
                recent.append(s); prev_fam = FAMILY.get(s, "?")
            prev_scheme = t.get("scheme"); continue
        window = set(recent[-5:])                          # posledne ~5 -> ziadne opakovanie sim
        cands = [s for s in SIMS if s not in window and FAMILY.get(s) != prev_fam]
        if not cands:
            cands = [s for s in SIMS if s not in window] or \
                    [s for s in SIMS if FAMILY.get(s) != prev_fam] or SIMS
        sim = random.choice(cands)
        scheme = random.choice([c for c in SCHEMES if c != prev_scheme] or SCHEMES)
        seed = random.randint(1, 99999)
        while seed in seeds:
            seed = random.randint(1, 99999)
        seeds.add(seed)
        t["sim"], t["scheme"], t["seed"] = sim, scheme, seed
        recent.append(sim); prev_fam = FAMILY.get(sim, "?"); prev_scheme = scheme


if __name__ == "__main__":
    main()
