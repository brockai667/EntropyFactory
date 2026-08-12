#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EyeHeist engine: plne automatizovane VIZUALNE puzzle shorts (ziadne LLM/AI obrazky).
Kazde video = intro + 2 kola (lahke vizualne + tazsie logicke) + outro. Kazdy puzzle je
generovany kodom so ZARUCENE spravnou odpovedou (seed -> nekonecna variacia, ziadne opakovanie).
Styl: zive gradient pozadie + biela karta + velky countdown ring + reveal. ~28-32 s (sweet spot).
"""
import asyncio, json, math, os, random, shutil, subprocess, sys, wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 30, 24000
BRAND = "@eyeheist"
VOICE = "en-US-GuyNeural"

def _ffmpeg():
    p = shutil.which("ffmpeg")
    if p: return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
FFMPEG = _ffmpeg()

def _font(px, bold=True):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()

# --- palety (bg gradient dvojica + akcent) — rotuju sa per video ---
PALETTES = [
    ((16, 24, 64), (99, 8, 120), (56, 224, 255)),     # navy->purple, cyan akcent
    ((10, 60, 40), (2, 16, 28), (255, 214, 74)),      # emerald->dark, gold
    ((70, 10, 40), (18, 6, 40), (255, 96, 160)),      # wine->indigo, pink
    ((8, 40, 90), (4, 10, 24), (120, 255, 170)),      # ocean->black, mint
    ((90, 40, 8), (30, 6, 30), (255, 170, 60)),       # ember->plum, orange
    ((24, 20, 80), (6, 30, 60), (170, 140, 255)),     # indigo->teal, lilac
]

def bg_img(pal):
    a, b, _ = pal
    g = np.linspace(0, 1, H)[:, None]
    arr = (np.array(a) * (1 - g[..., None]) + np.array(b) * g[..., None]).astype(np.uint8)
    arr = np.repeat(arr, W, axis=1).reshape(H, W, 3)
    rng = np.random.default_rng(5)
    arr = np.clip(arr.astype(np.int16) + rng.normal(0, 3, arr.shape).astype(np.int16), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")

def card_rect():
    return (90, 560, W - 90, 1660)     # biela karta s puzzle

def rounded(d, box, r, fill, outline=None, ow=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=ow)

def center_text(d, cx, cy, text, font, fill, stroke=0, sfill=None):
    d.text((cx, cy), text, font=font, fill=fill, anchor="mm",
           stroke_width=stroke, stroke_fill=sfill)

def fit_font(d, text, maxw, px):
    f = _font(px)
    while d.textlength(text, font=f) > maxw and px > 30:
        px -= 4; f = _font(px)
    return f

# ================= PUZZLE GENERATORY (seed -> zarucene spravna odpoved) =================
def gen_odd_one(rng, hard=False):
    """Mriezka smajlikov, jeden sa lisi (zamracene usta / zmurknute oko)."""
    cols, rows = (6, 8) if not hard else (7, 9)
    odd = (int(rng.integers(0, cols)), int(rng.integers(0, rows)))
    mode = "frown" if rng.random() < 0.6 else "wink"
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        cw, chh = (x1 - x0) / cols, (y1 - y0) / rows
        rad = int(min(cw, chh) * 0.36)
        for gy in range(rows):
            for gx in range(cols):
                cx, cy = x0 + cw * (gx + 0.5), y0 + chh * (gy + 0.5)
                is_odd = (gx, gy) == odd
                dr.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(255, 205, 60), outline=(60, 40, 0), width=3)
                ey = cy - rad * 0.25; ex = rad * 0.38
                if is_odd and mode == "wink":
                    dr.line((cx - ex - 6, ey, cx - ex + 6, ey), fill=(50, 30, 0), width=4)
                else:
                    dr.ellipse((cx - ex - 5, ey - 5, cx - ex + 5, ey + 5), fill=(50, 30, 0))
                dr.ellipse((cx + ex - 5, ey - 5, cx + ex + 5, ey + 5), fill=(50, 30, 0))
                my = cy + rad * 0.30
                if is_odd and mode == "frown":
                    dr.arc((cx - ex, my, cx + ex, my + rad * 0.5), 180, 360, fill=(50, 30, 0), width=4)
                else:
                    dr.arc((cx - ex, my - rad * 0.5, cx + ex, my), 0, 180, fill=(50, 30, 0), width=4)
                if is_odd and phase == "reveal":
                    p = min(1.0, t / 0.5)
                    rr = rad + 14 + 6 * math.sin(t * 6)
                    dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(235, 40, 40), width=int(8 * p) + 2)
    q = "Find the ODD one out!"
    vo_q = "One face is different. Find it!"
    vo_a = "There it is! Did you spot the " + ("grumpy one?" if mode == "frown" else "wink?")
    return {"draw": draw, "q": q, "vo_q": vo_q, "ans": "", "vo_a": vo_a}

def gen_count_squares(rng, hard=False):
    """Kolko stvorcov CELKOM v n*n mriezke (sum k^2) — klasika, vsetci povedia n^2."""
    n = 4 if not hard else 5
    total = sum(k * k for k in range(1, n + 1))
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        side = min(x1 - x0, y1 - y0) - 140
        gx0, gy0 = (x0 + x1) / 2 - side / 2, (y0 + y1) / 2 - side / 2 - 30
        step = side / n
        for i in range(n + 1):
            wln = 10 if i in (0, n) else 5
            dr.line((gx0, gy0 + i * step, gx0 + side, gy0 + i * step), fill=(30, 34, 60), width=wln)
            dr.line((gx0 + i * step, gy0, gx0 + i * step, gy0 + side), fill=(30, 34, 60), width=wln)
        if phase == "reveal":
            k = 1 + int(min(1.0, t / 1.4) * (n - 1))       # postupne zvyraznuj vacsie stvorce
            sz = k * step
            dr.rectangle((gx0, gy0, gx0 + sz, gy0 + sz), outline=(235, 40, 40), width=10)
            center_text(dr, (x0 + x1) / 2, y1 - 90, f"{k}x{k} squares count too!", _font(44), (30, 34, 60))
    q = f"How many squares IN TOTAL?"
    vo_q = f"How many squares in total? Careful - it's not {n * n}!"
    vo_a = f"Count every size, not just the small ones. It is {total}."
    return {"draw": draw, "q": q, "vo_q": vo_q, "ans": str(total), "vo_a": vo_a}

_ICONS = ["apple", "star", "moon"]
def _icon(dr, name, cx, cy, r, pal):
    if name == "apple":
        dr.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r), fill=(230, 60, 60), outline=(120, 20, 20), width=3)
        dr.line((cx, cy - r * 0.85, cx + r * 0.25, cy - r * 1.25), fill=(80, 120, 40), width=6)
    elif name == "star":
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        dr.polygon(pts, fill=(255, 200, 40), outline=(140, 100, 0))
    else:
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(150, 170, 255), outline=(70, 80, 160), width=3)
        dr.ellipse((cx - r * 0.35, cy - r, cx + r * 1.15, cy + r * 0.7), fill=(255, 255, 255))

def gen_icon_math(rng, hard=True):
    """Ikonova algebra s pascou na prednost nasobenia: A+A=?, B+B=?, A+B*A=?"""
    a = int(rng.integers(2, 7)); b = int(rng.integers(2, 7))
    ia, ib = rng.choice(len(_ICONS), size=2, replace=False)
    ia, ib = _ICONS[int(ia)], _ICONS[int(ib)]
    ans = a + b * a
    trap = (a + b) * a
    lines = [(ia, "+", ia, "=", str(2 * a)), (ib, "+", ib, "=", str(2 * b)), (ia, "+", ib, "x", None)]
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        rows_y = [y0 + 170, y0 + 420, y0 + 670]
        f = _font(96)
        for li, (s1, op, s2, op2, val) in enumerate(lines):
            cy = rows_y[li]; cx = (x0 + x1) / 2
            if li < 2:
                _icon(dr, s1, cx - 260, cy, 62, None); center_text(dr, cx - 140, cy, op, f, (30, 34, 60))
                _icon(dr, s2, cx - 20, cy, 62, None); center_text(dr, cx + 110, cy, "=", f, (30, 34, 60))
                center_text(dr, cx + 240, cy, val, f, (30, 34, 60))
            else:
                _icon(dr, s1, cx - 330, cy, 62, None); center_text(dr, cx - 210, cy, "+", f, (30, 34, 60))
                _icon(dr, s2, cx - 90, cy, 62, None); center_text(dr, cx + 30, cy, "x", f, (200, 40, 40))
                _icon(dr, s1, cx + 150, cy, 62, None); center_text(dr, cx + 280, cy, "= ?", f, (30, 34, 60))
        if phase == "reveal":
            center_text(dr, (x0 + x1) / 2, y1 - 170, f"NOT {trap}!", _font(56), (200, 40, 40))
    q = "Solve the LAST line!"
    vo_q = "Two clues, one trap. What does the last line equal?"
    vo_a = f"Multiplication first! {b} times {a}, plus {a}, is {ans}. Did the trap get you?"
    return {"draw": draw, "q": q, "vo_q": vo_q, "ans": str(ans), "vo_a": vo_a}

def gen_missing_num(rng, hard=True):
    """3x3 mriezka: v kazdom riadku a+b=c. Posledne cislo chyba."""
    grid = []
    for _ in range(3):
        a = int(rng.integers(3, 30)); b = int(rng.integers(3, 30))
        grid.append([a, b, a + b])
    ans = grid[2][2]
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        side = min(x1 - x0, y1 - y0) - 150
        gx0, gy0 = (x0 + x1) / 2 - side / 2, (y0 + y1) / 2 - side / 2 - 20
        step = side / 3
        f = _font(88)
        for r in range(3):
            for c in range(3):
                cx, cy = gx0 + step * (c + 0.5), gy0 + step * (r + 0.5)
                rounded(dr, (cx - step * 0.44, cy - step * 0.44, cx + step * 0.44, cy + step * 0.44), 22,
                        (244, 246, 252), outline=(30, 34, 60), ow=4)
                val = str(grid[r][c])
                if r == 2 and c == 2:
                    if phase == "reveal":
                        p = min(1.0, t / 0.4)
                        center_text(dr, cx, cy, val, _font(int(88 * (0.6 + 0.4 * p))), (20, 150, 70))
                    else:
                        center_text(dr, cx, cy, "?", f, (200, 40, 40))
                else:
                    center_text(dr, cx, cy, val, f, (30, 34, 60))
    q = "What replaces the ?"
    vo_q = "Every row hides the same rule. What number replaces the question mark?"
    vo_a = f"Each row adds up: first plus second equals third. {grid[2][0]} plus {grid[2][1]} is {ans}."
    return {"draw": draw, "q": q, "vo_q": vo_q, "ans": str(ans), "vo_a": vo_a}

EASY = [gen_odd_one]
HARD = [gen_count_squares, gen_icon_math, gen_missing_num]

# ================= AUDIO =================
async def _tts_async(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="+4%").save(path)

def tts(text, path):
    asyncio.run(_tts_async(text, path))
    raw = subprocess.run([FFMPEG, "-i", path, "-f", "s16le", "-acodec", "pcm_s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(raw.stdout, np.int16).astype(np.float32) / 32768.0

def sfx_tick():
    t = np.linspace(0, 0.07, int(SR * 0.07), False)
    return (np.sin(2 * np.pi * 1250 * t) * np.exp(-t * 60) * 0.5).astype(np.float32)

def sfx_ding():
    t = np.linspace(0, 0.7, int(SR * 0.7), False)
    s = (np.sin(2 * np.pi * 1318 * t) + 0.6 * np.sin(2 * np.pi * 1760 * t)) * np.exp(-t * 5)
    return (s * 0.4).astype(np.float32)

def sfx_whoosh():
    n = int(SR * 0.4); rng = np.random.default_rng(3)
    s = rng.normal(0, 1, n).astype(np.float32)
    env = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (s * env * 0.18).astype(np.float32)

def load_music(total_n):
    mdir = os.path.join(ROOT, "assets", "music")
    tracks = [f for f in os.listdir(mdir) if f.endswith(".mp3")] if os.path.isdir(mdir) else []
    if not tracks:
        return np.zeros(total_n, np.float32), ""
    tr = random.choice(tracks)
    raw = subprocess.run([FFMPEG, "-i", os.path.join(mdir, tr), "-f", "s16le", "-acodec", "pcm_s16le",
                          "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    m = np.frombuffer(raw.stdout, np.int16).astype(np.float32) / 32768.0
    if len(m) < total_n:
        m = np.tile(m, total_n // max(1, len(m)) + 1)
    m = m[:total_n] * 0.14
    fade = int(SR * 1.2)
    if len(m) > fade:
        m[-fade:] *= np.linspace(1, 0, fade)
    return m, tr

# ================= TIMELINE + RENDER =================
COUNTDOWN = 5.0

def build_video(seed, out_mp4):
    rng = np.random.default_rng(seed)
    pal = PALETTES[seed % len(PALETTES)]
    p1 = EASY[0](rng, hard=False)
    p2 = HARD[int(rng.integers(0, len(HARD)))](rng, hard=True)

    tmp = os.path.join(ROOT, "output", f"_tts_{seed}")
    os.makedirs(tmp, exist_ok=True)
    def T(name, text):
        return tts(text, os.path.join(tmp, name + ".mp3"))
    vo = {
        "intro": T("intro", "Ninety nine percent fail this. Round one!"),
        "q1": T("q1", p1["vo_q"]), "a1": T("a1", p1["vo_a"]),
        "r2": T("r2", "Round two. Harder."),
        "q2": T("q2", p2["vo_q"]), "a2": T("a2", p2["vo_a"]),
        "outro": T("outro", "Comment your score. Follow for a daily test."),
    }
    dur = lambda k: len(vo[k]) / SR
    # sekcie: (meno, trvanie, puzzle, faza)
    secs = []
    secs.append(("intro", max(1.5, dur("intro") + 0.2), None, "intro"))
    secs.append(("q1", max(1.8, dur("q1") + 0.25), p1, "show"))
    secs.append(("cd1", COUNTDOWN, p1, "count"))
    secs.append(("a1", max(2.2, min(dur("a1") + 0.35, 4.6)), p1, "reveal"))
    secs.append(("r2", max(1.2, dur("r2") + 0.2), None, "round2"))
    secs.append(("q2", max(1.8, dur("q2") + 0.25), p2, "show"))
    secs.append(("cd2", COUNTDOWN, p2, "count"))
    secs.append(("a2", max(2.4, min(dur("a2") + 0.35, 5.2)), p2, "reveal"))
    secs.append(("outro", max(2.0, dur("outro") + 0.3), None, "outro"))
    total = sum(s[1] for s in secs)
    n = int(total * FPS)

    # audio mix
    audio = np.zeros(int(total * SR) + SR, np.float32)
    t0 = 0.0
    tick, ding, whoosh = sfx_tick(), sfx_ding(), sfx_whoosh()
    for name, sd, pz, phase in secs:
        s0 = int(t0 * SR)
        if name in vo:
            seg = vo[name]; audio[s0:s0 + len(seg)] += seg
        if phase == "count":
            for k in range(int(COUNTDOWN)):
                ks = s0 + int(k * SR)
                audio[ks:ks + len(tick)] += tick
        if phase == "reveal":
            audio[s0:s0 + len(ding)] += ding
        if phase in ("intro", "round2"):
            audio[s0:s0 + len(whoosh)] += whoosh
        t0 += sd
    music, track = load_music(len(audio))
    mix = np.clip(audio * 0.95 + music, -1, 1)
    wav = os.path.join(tmp, "mix.wav")
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((mix * 32767).astype("<i2").tobytes())

    BG = bg_img(pal)
    acc = pal[2]
    fQ = _font(76); fBig = _font(200); fT = _font(120); fS = _font(46)
    wm = _font(42)
    card = card_rect()

    p = subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", out_mp4],
                         stdin=subprocess.PIPE)
    f_idx = 0
    sec_start = 0.0
    for name, sd, pz, phase in secs:
        frames = int(round(sd * FPS))
        for fi in range(frames):
            t = fi / FPS
            fr = BG.copy(); d = ImageDraw.Draw(fr)
            if phase == "intro":
                pulse = 1 + 0.04 * math.sin(t * 5)
                center_text(d, W / 2, 700, "EYE TEST", _font(int(170 * pulse)), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                center_text(d, W / 2, 920, "99% FAIL", _font(90), acc, stroke=8, sfill=(0, 0, 0))
                center_text(d, W / 2, 1120, "2 rounds. Beat the clock.", fS, (235, 238, 250))
            elif phase == "round2":
                center_text(d, W / 2, 880, "ROUND 2", _font(150), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                center_text(d, W / 2, 1080, "HARDER.", _font(90), acc, stroke=8, sfill=(0, 0, 0))
            elif phase == "outro":
                center_text(d, W / 2, 760, "SCORE?", _font(140), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                center_text(d, W / 2, 960, "0/2  1/2  2/2", _font(84), acc, stroke=6, sfill=(0, 0, 0))
                center_text(d, W / 2, 1160, "Comment your score", fS, (235, 238, 250))
                center_text(d, W / 2, 1290, "+ follow for a daily test", fS, (235, 238, 250))
            else:
                # spolocny layout kola: otazka hore, karta, timer
                rounded(d, card, 46, (250, 250, 252), outline=(15, 18, 34), ow=6)
                qf = fit_font(d, pz["q"], 900, 82)
                center_text(d, W / 2, 350, pz["q"], qf, (255, 255, 255), stroke=8, sfill=(0, 0, 0))
                inner = (card[0] + 30, card[1] + 30, card[2] - 30, card[3] - 30)
                pz["draw"](inner, d, phase, t)
                if phase == "count":
                    left = max(0.0, COUNTDOWN - t)
                    frac = left / COUNTDOWN
                    cx, cy, r = W / 2, 1790, 92
                    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(0, 0, 0))
                    d.arc((cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8), -90, -90 + 360 * frac, fill=acc, width=14)
                    center_text(d, cx, cy, str(int(math.ceil(left))), _font(96), (255, 255, 255))
                elif phase == "reveal":
                    if pz["ans"]:
                        pp = min(1.0, t / 0.35)
                        center_text(d, W / 2, 1790, pz["ans"], _font(int(150 * (0.5 + 0.5 * pp))), (60, 235, 140), stroke=10, sfill=(0, 0, 0))
                    else:
                        center_text(d, W / 2, 1790, "FOUND IT!", _font(84), (60, 235, 140), stroke=8, sfill=(0, 0, 0))
                elif phase == "show":
                    center_text(d, W / 2, 1790, "get ready...", fS, (235, 238, 250))
            center_text(d, W / 2, H - 46, BRAND, wm, (200, 205, 220))
            try:
                p.stdin.write(np.asarray(fr, np.uint8).tobytes())
            except (BrokenPipeError, OSError):
                break
            f_idx += 1
        sec_start += sd
    try:
        p.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    p.wait()
    shutil.rmtree(tmp, ignore_errors=True)
    return {"total": total, "p2_type": p2["vo_q"][:40], "music": track}

if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    info = build_video(int(sys.argv[1]) if len(sys.argv) > 1 else 1,
                       os.path.join(ROOT, "output", "eyeheist_sample.mp4"))
    print("HOTOVO", info)
