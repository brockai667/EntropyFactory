#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""EyeHeist engine v2 — brand vizual (oko, navy->fialova, cyan akcent) + zive animacie.
Kazde video: BLIKAJUCE OKO intro -> kolo 1 (vizualny test: odtien / ikony / skryte cislo)
-> countdown ring (cyan->cervena) -> reveal s flashom -> kolo 2 (logika: icon-math /
missing-number / count-squares) -> score outro s okom. Vsetko kreslene kodom, odpoved
ZARUCENE spravna (seed -> nekonecna variacia). ~35-40 s.
"""
import asyncio, colorsys, json, math, os, random, shutil, subprocess, sys, wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 30, 24000
BRAND = "@eyeheist"
VOICE = "en-US-GuyNeural"

NAVY = (16, 18, 52); PURPLE = (88, 24, 130); CYAN = (56, 224, 255)
INKD = (22, 24, 48)                      # tmavy text na bielej karte
GOOD = (60, 235, 140); BAD = (255, 82, 82); AMBER = (255, 196, 60)

def _ffmpeg():
    p = shutil.which("ffmpeg")
    if p: return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"
FFMPEG = _ffmpeg()

def _font(px):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", r"C:\Windows\Fonts\arialbd.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()

clamp = lambda v, a=0.0, b=1.0: max(a, min(b, v))
def ease_back(t, s=1.70158):
    t = clamp(t) - 1.0
    return t * t * ((s + 1) * t + s) + 1

# brand pozadie: navy -> fialova + jemna vinetacia (3 varianty toho isteho sveta)
_BGV = [((16, 18, 52), (88, 24, 130)), ((10, 16, 44), (24, 60, 110)), ((30, 14, 60), (14, 20, 56))]
def bg_img(seed):
    a, b = _BGV[seed % len(_BGV)]
    g = np.linspace(0, 1, H)[:, None]
    arr = (np.array(a) * (1 - g[..., None]) + np.array(b) * g[..., None])
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H * 0.45) / (H * 0.7)) ** 2)[..., None]
    arr = arr * (1.06 - 0.34 * np.clip(d - 0.35, 0, 1))
    rng = np.random.default_rng(5)
    arr = np.clip(arr + rng.normal(0, 2.5, arr.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")

def draw_eye(d, cx, cy, rw, blink=0.0, look=(0, 0)):
    """Brand oko (ako avatar): biela mandla + cyan iris + zrenicka + highlight; blink 0..1 zaviera."""
    rh = rw * 0.62
    d.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=(250, 250, 252), outline=(10, 12, 30), width=max(3, int(rw * 0.075)))
    ir = rw * 0.42
    ix, iy = cx + look[0] * rw * 0.18, cy + look[1] * rh * 0.2
    d.ellipse((ix - ir, iy - ir, ix + ir, iy + ir), fill=CYAN, outline=(10, 12, 30), width=max(3, int(rw * 0.05)))
    pu = ir * 0.46
    d.ellipse((ix - pu, iy - pu, ix + pu, iy + pu), fill=(8, 10, 22))
    hl = ir * 0.2
    d.ellipse((ix - ir * 0.45 - hl, iy - ir * 0.5 - hl, ix - ir * 0.45 + hl, iy - ir * 0.5 + hl), fill=(255, 255, 255))
    if blink > 0.02:                                     # viecko zhora (farba pozadia-ish)
        lid = rh * 2 * clamp(blink)
        d.ellipse((cx - rw - 6, cy - rh - 6, cx + rw + 6, cy - rh - 6 + lid), fill=(30, 20, 62))

def card_rect():
    return (84, 545, W - 84, 1655)

def rounded(d, box, r, fill, outline=None, ow=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=ow)

def ctext(d, cx, cy, text, font, fill, stroke=0, sfill=None):
    d.text((cx, cy), text, font=font, fill=fill, anchor="mm", stroke_width=stroke, stroke_fill=sfill)

def fit_font(d, text, maxw, px):
    f = _font(px)
    while d.textlength(text, font=f) > maxw and px > 30:
        px -= 4; f = _font(px)
    return f

def cell_rev(t, idx, per=0.012, dur=0.24):
    """Pop-in vlna: kazda bunka nabehne o kusok neskor (scale 0->1 s overshootom)."""
    return ease_back(clamp((t - idx * per) / dur))

# ================= PUZZLE GENERATORY =================
def _hsv(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, clamp(s), clamp(v))
    return (int(r * 255), int(g * 255), int(b * 255))

def gen_odd_shade(rng, hard=False):
    """Klasika: mriezka farebnych dlazdic, JEDNA ma iny odtien."""
    cols, rows = (6, 9) if not hard else (7, 10)
    odd = (int(rng.integers(0, cols)), int(rng.integers(0, rows)))
    hue = float(rng.random()); dv = 0.09 if not hard else 0.062
    base = _hsv(hue, 0.78, 0.92); oddc = _hsv(hue, 0.78, 0.92 - dv)
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        cw, chh = (x1 - x0) / cols, (y1 - y0) / rows
        for gy in range(rows):
            for gx in range(cols):
                idx = gy * cols + gx
                rv = cell_rev(t, idx) if phase == "show" else 1.0
                if rv <= 0: continue
                cx, cy = x0 + cw * (gx + 0.5), y0 + chh * (gy + 0.5)
                w2, h2 = cw * 0.44 * rv, chh * 0.44 * rv
                is_odd = (gx, gy) == odd
                col = oddc if is_odd else base
                if phase == "reveal" and not is_odd:
                    col = tuple(int(c * 0.45) for c in col)          # ostatne stlmit
                rounded(dr, (cx - w2, cy - h2, cx + w2, cy + h2), int(14 * rv), col)
                if is_odd and phase == "reveal":
                    rr = max(w2, h2) + 12 + 5 * math.sin(t * 7)
                    dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=BAD, width=9)
    q = "Find the DIFFERENT shade!"
    return {"draw": draw, "q": q, "vo_q": "One tile is a different shade. Find it!",
            "ans": "", "vo_a": "There it is. Sharp eyes!"}

_FAMS = ["smiley", "heart", "star"]
def _draw_icon(dr, fam, cx, cy, rad, odd=False):
    if fam == "smiley":
        dr.ellipse((cx - rad, cy - rad, cx + rad, cy + rad), fill=(255, 205, 60), outline=(60, 40, 0), width=3)
        ey = cy - rad * 0.25; ex = rad * 0.38
        dr.ellipse((cx - ex - 5, ey - 5, cx - ex + 5, ey + 5), fill=(50, 30, 0))
        dr.ellipse((cx + ex - 5, ey - 5, cx + ex + 5, ey + 5), fill=(50, 30, 0))
        my = cy + rad * 0.30
        if odd:
            dr.arc((cx - ex, my, cx + ex, my + rad * 0.5), 180, 360, fill=(50, 30, 0), width=4)
        else:
            dr.arc((cx - ex, my - rad * 0.5, cx + ex, my), 0, 180, fill=(50, 30, 0), width=4)
    elif fam == "heart":
        r = rad * 0.55
        ang = 8 if odd else 0
        pts = []
        for i in range(60):
            th = i / 59 * 2 * math.pi
            x = 16 * math.sin(th) ** 3
            y = -(13 * math.cos(th) - 5 * math.cos(2 * th) - 2 * math.cos(3 * th) - math.cos(4 * th))
            a = math.radians(ang)
            xr, yr = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            pts.append((cx + xr * r / 16, cy + yr * r / 16))
        dr.polygon(pts, fill=(240, 70, 90) if not odd else (240, 70, 90), outline=(120, 10, 30))
    else:
        n = 5 if not odd else 4                             # odd hviezda ma 4 cipy
        pts = []
        for i in range(n * 2):
            a = -math.pi / 2 + i * math.pi / n
            rr = rad if i % 2 == 0 else rad * 0.45
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        dr.polygon(pts, fill=(255, 200, 40), outline=(140, 100, 0))

def gen_odd_icon(rng, hard=False):
    fam = _FAMS[int(rng.integers(0, len(_FAMS)))]
    cols, rows = (7, 10) if not hard else (8, 11)
    odd = (int(rng.integers(0, cols)), int(rng.integers(0, rows)))
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        cw, chh = (x1 - x0) / cols, (y1 - y0) / rows
        for gy in range(rows):
            for gx in range(cols):
                idx = gy * cols + gx
                rv = cell_rev(t, idx) if phase == "show" else 1.0
                if rv <= 0: continue
                cx, cy = x0 + cw * (gx + 0.5), y0 + chh * (gy + 0.5)
                rad = min(cw, chh) * 0.37 * rv
                is_odd = (gx, gy) == odd
                _draw_icon(dr, fam, cx, cy, rad, odd=is_odd)
                if is_odd and phase == "reveal":
                    rr = rad + 13 + 5 * math.sin(t * 7)
                    dr.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=BAD, width=9)
    hint = {"smiley": "one face is grumpy", "heart": "one heart is tilted", "star": "one star lost a point"}[fam]
    return {"draw": draw, "q": "Find the ODD one out!", "vo_q": "One of these is different. Find the odd one out!",
            "ans": "", "vo_a": f"Got it? Exactly - {hint}!"}

def gen_hidden_number(rng, hard=False):
    """Pole bodiek, cast tvori CISLO v inom odtieni — virusovy 'what number do you see'."""
    num = str(int(rng.integers(10, 100)))
    hue = float(rng.random())
    base = _hsv(hue, 0.72, 0.90); numc = _hsv(hue, 0.72, 0.90 - (0.10 if hard else 0.13))
    mask = Image.new("L", (300, 300), 0)
    md = ImageDraw.Draw(mask)
    fpx = 260; mf = _font(fpx)                            # auto-fit: cislo vyplni masku
    while md.textlength(num, font=mf) > 268 and fpx > 80:
        fpx -= 10; mf = _font(fpx)
    md.text((150, 150), num, font=mf, fill=255, anchor="mm")
    n = 26
    mgrid = np.asarray(mask.resize((n, n), Image.BILINEAR))   # plynule vzorkovanie (citatelne cifry)
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        side = min(x1 - x0, y1 - y0) - 60
        gx0, gy0 = (x0 + x1) / 2 - side / 2, (y0 + y1) / 2 - side / 2
        step = side / n
        for gy in range(n):
            for gx in range(n):
                idx = gy * n + gx
                rv = cell_rev(t, idx, per=0.0016, dur=0.2) if phase == "show" else 1.0
                if rv <= 0: continue
                inside = mgrid[gy, gx] > 90
                col = numc if inside else base
                if phase == "reveal" and inside:
                    col = (255, 255, 255)                     # cislo zasvieti
                cx, cy = gx0 + step * (gx + 0.5), gy0 + step * (gy + 0.5)
                r = step * 0.42 * rv
                dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    return {"draw": draw, "q": "What NUMBER do you see?", "vo_q": "There is a number hiding in the dots. What is it?",
            "ans": num, "vo_a": f"It was {num}! If you saw it instantly, your eyes are elite."}

def gen_count_squares(rng, hard=True):
    n = 4 if not hard else 5
    total = sum(k * k for k in range(1, n + 1))
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        side = min(x1 - x0, y1 - y0) - 150
        gx0, gy0 = (x0 + x1) / 2 - side / 2, (y0 + y1) / 2 - side / 2 - 30
        step = side / n
        for i in range(n + 1):
            wln = 10 if i in (0, n) else 5
            dr.line((gx0, gy0 + i * step, gx0 + side, gy0 + i * step), fill=INKD, width=wln)
            dr.line((gx0 + i * step, gy0, gx0 + i * step, gy0 + side), fill=INKD, width=wln)
        if phase == "reveal":
            k = 1 + int(min(1.0, t / 1.4) * (n - 1))
            dr.rectangle((gx0, gy0, gx0 + k * step, gy0 + k * step), outline=BAD, width=10)
            ctext(dr, (x0 + x1) / 2, y1 - 90, f"{k}x{k} squares count too!", _font(44), INKD)
    return {"draw": draw, "q": "How many squares IN TOTAL?", "vo_q": f"How many squares in total? Careful - it's not {n*n}!",
            "ans": str(total), "vo_a": f"Count every size, not just the small ones. It is {total}."}

_MICONS = ["apple", "star", "moon"]
def _micon(dr, name, cx, cy, r):
    if name == "apple":
        dr.ellipse((cx - r, cy - r * 0.85, cx + r, cy + r), fill=(230, 60, 60), outline=(120, 20, 20), width=3)
        dr.line((cx, cy - r * 0.85, cx + r * 0.25, cy - r * 1.25), fill=(80, 120, 40), width=6)
    elif name == "star":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        dr.polygon(pts, fill=(255, 200, 40), outline=(140, 100, 0))
    else:
        dr.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(150, 170, 255), outline=(70, 80, 160), width=3)
        dr.ellipse((cx - r * 0.35, cy - r, cx + r * 1.15, cy + r * 0.7), fill=(255, 255, 255))

def gen_icon_math(rng, hard=True):
    a = int(rng.integers(3, 10)); b = int(rng.integers(3, 10))
    pick = rng.choice(len(_MICONS), size=2, replace=False)
    ia, ib = _MICONS[int(pick[0])], _MICONS[int(pick[1])]
    ans = a + b * a; trap = (a + b) * a
    def draw(card, dr, phase, t):
        x0, y0, x1, y1 = card
        rows_y = [y0 + 180, y0 + 440, y0 + 700]
        f = _font(96)
        rows = [(ia, ia, str(2 * a), False), (ib, ib, str(2 * b), False), (ia, ib, None, True)]
        for li, (s1, s2, val, last) in enumerate(rows):
            rv = ease_back(clamp((t - li * 0.14) / 0.3)) if phase == "show" else 1.0
            if rv <= 0: continue
            cy = rows_y[li]; cx = (x0 + x1) / 2
            rr = 62 * rv
            if not last:
                _micon(dr, s1, cx - 260, cy, rr); ctext(dr, cx - 140, cy, "+", f, INKD)
                _micon(dr, s2, cx - 20, cy, rr); ctext(dr, cx + 110, cy, "=", f, INKD)
                ctext(dr, cx + 240, cy, val, f, INKD)
            else:
                _micon(dr, s1, cx - 330, cy, rr); ctext(dr, cx - 210, cy, "+", f, INKD)
                _micon(dr, s2, cx - 90, cy, rr); ctext(dr, cx + 30, cy, "x", f, BAD)
                _micon(dr, s1, cx + 150, cy, rr); ctext(dr, cx + 280, cy, "= ?", f, INKD)
        if phase == "reveal":
            ctext(dr, (x0 + x1) / 2, y1 - 160, f"NOT {trap}!", _font(56), BAD)
    return {"draw": draw, "q": "Solve the LAST line!", "vo_q": "Two clues, one trap. What does the last line equal?",
            "ans": str(ans), "vo_a": f"Multiplication first! {b} times {a}, plus {a}, is {ans}. Did the trap get you?"}

def gen_missing_num(rng, hard=True):
    mul = bool(hard and rng.random() < 0.5)              # tazsia varianta: a x b = c
    grid = []
    for _ in range(3):
        if mul:
            a = int(rng.integers(3, 13)); b = int(rng.integers(3, 13))
            grid.append([a, b, a * b])
        else:
            a = int(rng.integers(7, 60)); b = int(rng.integers(7, 60))
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
                idx = r * 3 + c
                rv = cell_rev(t, idx, per=0.05, dur=0.28) if phase == "show" else 1.0
                if rv <= 0: continue
                cx, cy = gx0 + step * (c + 0.5), gy0 + step * (r + 0.5)
                w2 = step * 0.44 * rv
                rounded(dr, (cx - w2, cy - w2, cx + w2, cy + w2), 22, (244, 246, 252), outline=INKD, ow=4)
                val = str(grid[r][c])
                if r == 2 and c == 2:
                    if phase == "reveal":
                        p = clamp(t / 0.4)
                        ctext(dr, cx, cy, val, _font(int(88 * (0.6 + 0.4 * p))), (20, 150, 70))
                    else:
                        ctext(dr, cx, cy, "?", f, BAD)
                else:
                    ctext(dr, cx, cy, val, f, INKD)
    vo_a = (f"Each row multiplies: {grid[2][0]} times {grid[2][1]} is {ans}." if mul
            else f"Each row adds up: {grid[2][0]} plus {grid[2][1]} is {ans}.")
    return {"draw": draw, "q": "What replaces the ?", "vo_q": "Every row hides the same rule. What replaces the question mark?",
            "ans": str(ans), "vo_a": vo_a}

EASY = [gen_odd_shade, gen_odd_icon, gen_hidden_number]
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
    p1 = EASY[int(rng.integers(0, len(EASY)))](rng, hard=False)
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
    secs = []
    secs.append(("intro", max(1.7, dur("intro") + 0.2), None, "intro"))
    secs.append(("q1", max(1.9, dur("q1") + 0.25), p1, "show"))
    secs.append(("cd1", COUNTDOWN, p1, "count"))
    secs.append(("a1", max(2.2, min(dur("a1") + 0.35, 4.6)), p1, "reveal"))
    secs.append(("r2", max(1.2, dur("r2") + 0.2), None, "round2"))
    secs.append(("q2", max(1.9, dur("q2") + 0.25), p2, "show"))
    secs.append(("cd2", COUNTDOWN, p2, "count"))
    secs.append(("a2", max(2.4, min(dur("a2") + 0.35, 5.2)), p2, "reveal"))
    secs.append(("outro", max(2.2, dur("outro") + 0.3), None, "outro"))
    total = sum(s[1] for s in secs)
    n = int(total * FPS)

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

    BG = bg_img(seed)
    fS = _font(46); wm = _font(42)
    card = card_rect()

    p = subprocess.Popen([FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", out_mp4],
                         stdin=subprocess.PIPE)
    for name, sd, pz, phase in secs:
        frames = int(round(sd * FPS))
        for fi in range(frames):
            t = fi / FPS
            fr = BG.copy(); d = ImageDraw.Draw(fr)
            if phase == "intro":
                # frame 0 = PLNY cover (IG/TikTok/YT grid berie prvy frame!); zmurknutie v strede intra
                bl = math.sin((t - 0.5) / 0.4 * math.pi) if 0.5 < t < 0.9 else 0.0
                look = (math.sin(t * 2.2) * 0.5, 0)
                draw_eye(d, W / 2, 560, 300, blink=bl, look=look)
                ctext(d, W / 2, 1050, "EYE TEST", _font(170), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                ctext(d, W / 2, 1240, "99% FAIL", _font(96), CYAN, stroke=8, sfill=(0, 0, 0))
                ctext(d, W / 2, 1400, "2 rounds. Beat the clock.", fS, (232, 235, 250))
            elif phase == "round2":
                pop = ease_back(clamp(t / 0.3))
                draw_eye(d, W / 2, 500, 190, look=(0, 0.35))
                ctext(d, W / 2, 950, "ROUND 2", _font(int(150 * pop) or 1), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                ctext(d, W / 2, 1130, "HARDER.", _font(88), AMBER, stroke=8, sfill=(0, 0, 0))
            elif phase == "outro":
                draw_eye(d, W / 2, 520, 230, look=(0, 0.2))
                ctext(d, W / 2, 980, "SCORE?", _font(140), (255, 255, 255), stroke=10, sfill=(0, 0, 0))
                ctext(d, W / 2, 1170, "0/2   1/2   2/2", _font(88), CYAN, stroke=6, sfill=(0, 0, 0))
                ctext(d, W / 2, 1340, "Comment your score", fS, (232, 235, 250))
                ctext(d, W / 2, 1450, "+ follow for a daily test", fS, (232, 235, 250))
            else:
                bree = 1 + 0.006 * math.sin(t * 1.7)          # karta jemne dycha
                cx0, cy0, cx1, cy1 = card
                mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
                wc, hc = (cx1 - cx0) / 2 * bree, (cy1 - cy0) / 2 * bree
                cardb = (mx - wc, my - hc, mx + wc, my + hc)
                rounded(d, cardb, 46, (250, 250, 252), outline=(8, 10, 26), ow=6)
                qf = fit_font(d, pz["q"], 900, 82)
                ctext(d, W / 2, 340, pz["q"], qf, (255, 255, 255), stroke=8, sfill=(0, 0, 0))
                inner = (cardb[0] + 28, cardb[1] + 28, cardb[2] - 28, cardb[3] - 28)
                pz["draw"](inner, d, phase, t)
                if phase == "count":
                    left = max(0.0, COUNTDOWN - t)
                    frac = left / COUNTDOWN
                    ring = CYAN if frac > 0.4 else (AMBER if frac > 0.2 else BAD)
                    pulse = 1 + 0.06 * math.sin(t * math.pi * 2)
                    cxr, cyr, r = W / 2, 1788, 92 * pulse
                    d.ellipse((cxr - r, cyr - r, cxr + r, cyr + r), fill=(0, 0, 0))
                    d.arc((cxr - r + 8, cyr - r + 8, cxr + r - 8, cyr + r - 8), -90, -90 + 360 * frac, fill=ring, width=14)
                    ctext(d, cxr, cyr, str(int(math.ceil(left))), _font(96), (255, 255, 255))
                elif phase == "reveal":
                    if t < 0.1:                                # flash
                        fl = Image.new("RGB", (W, H), (255, 255, 255))
                        fr = Image.blend(fr, fl, 0.55 * (1 - t / 0.1)); d = ImageDraw.Draw(fr)
                    if pz["ans"]:
                        pp = clamp(t / 0.35)
                        ctext(d, W / 2, 1788, pz["ans"], _font(int(150 * (0.5 + 0.5 * pp)) or 1), GOOD, stroke=10, sfill=(0, 0, 0))
                    else:
                        ctext(d, W / 2, 1788, "FOUND IT!", _font(84), GOOD, stroke=8, sfill=(0, 0, 0))
                elif phase == "show":
                    ctext(d, W / 2, 1788, "get ready...", fS, (232, 235, 250))
            ctext(d, W / 2, H - 44, BRAND, wm, (205, 210, 228))
            try:
                p.stdin.write(np.asarray(fr, np.uint8).tobytes())
            except (BrokenPipeError, OSError):
                break
    try:
        p.stdin.close()
    except (BrokenPipeError, OSError):
        pass
    p.wait()
    shutil.rmtree(tmp, ignore_errors=True)
    return {"total": total, "music": track}

if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "output"), exist_ok=True)
    info = build_video(int(sys.argv[1]) if len(sys.argv) > 1 else 1,
                       os.path.join(ROOT, "output", "eyeheist_sample.mp4"))
    print("HOTOVO", info)
