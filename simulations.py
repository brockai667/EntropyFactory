# -*- coding: utf-8 -*-
"""Entropy - hypnoticke fyzikalne/matematicke simulacie renderovane na cierno so ziarivymi stopami.
Kazda sim je generator co yielduje uint8 RGB framy (H x W x 3): aditivny canvas + decay = ziarive
stopy, lahky bloom cez PIL (glow). Klucom ku krase je KOHERENTNY symetricky pohyb (vlny, nie sum).

UPGRADE: 3D atraktory sa TOCIA (turntable) + dychaju (zoom) + hlbkove tienovanie -> stale sa nieco
deje; nove simy double_pendulum (butterfly effect), clifford_morph (morfujuci tvar), galaxy_spiral."""
import numpy as np

try:
    from PIL import Image, ImageFilter
    _PIL = True
except Exception:
    _PIL = False


def _tonemap(canvas, exposure=1.0, bloom=2.0):
    img = 1.0 - np.exp(-np.clip(canvas, 0, None) * exposure)
    u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    if _PIL and bloom:
        im = Image.fromarray(u8, "RGB")
        glow = im.filter(ImageFilter.GaussianBlur(radius=bloom))
        a = np.asarray(im, np.float32); b = np.asarray(glow, np.float32)
        out = 255 - (255 - a) * (255 - b) / 255.0
        u8 = np.clip(out, 0, 255).astype(np.uint8)
    return u8


def _cool_warm(n):
    t = np.abs(np.linspace(-1, 1, n))
    return np.clip(np.stack([0.55 + 0.45 * t, 0.72 - 0.25 * t, 1.00 - 0.70 * t], 1), 0.12, 1.0)


def _ring(cen, R, W, H):
    th = np.linspace(0, 2 * np.pi, 1500)
    rx = (cen[0] + R * np.cos(th)).astype(np.int32)
    ry = (cen[1] + R * np.sin(th)).astype(np.int32)
    ok = (rx >= 0) & (rx < W) & (ry >= 0) & (ry < H)
    return rx[ok], ry[ok]


def stream_sphere(W=1080, H=1920, fps=30, duration=18, n=5000, seed=7, **_kw):
    """Pyrotas styl: gulicky padaju zhora (NIZKA poc. rychlost + gravitacia = na zaciatku vidno PADANIE),
    od stredu vejara von (zaciatok = tenka ciara), koherentny vejar -> intrikatna symetricka siet.
    Lava=tepla oranzova, prava=studena modra, biele jadro."""
    cen = np.array([W / 2.0, H / 2.0])
    R = min(W, H) * 0.46
    nf = int(fps * duration)
    half = n // 2; n = half * 2
    base = np.pi / 2                                      # priamo nadol (+y)
    mag = np.linspace(0.02, 1.0, half) * np.deg2rad(42)  # vejar uhlov (od stredu von)
    ang = np.concatenate([base - mag, base + mag])       # symetricke pary: prva polka lava, druha prava
    spd = R * 0.004                                       # NIZKA poc. rychlost -> gravitacia dominuje = padanie
    vel = np.stack([np.cos(ang), np.sin(ang)], 1) * spd
    g_high = R * 0.0017; g_low = R * 0.0002              # silna gravitacia (padanie) -> slaba (koherentny vejar)
    grav_until = int(nf * 0.22)
    warm = np.array([1.0, 0.42, 0.10]); cool = np.array([0.22, 0.55, 1.0])
    col = np.vstack([np.tile(warm, (half, 1)), np.tile(cool, (half, 1))])  # lava tepla, prava studena
    pos = np.tile([cen[0], cen[1] - R * 0.93], (n, 1)).astype(np.float64)
    active = np.zeros(n, bool)
    rel = np.empty(n, np.int64); rel[0::2] = np.arange(half); rel[1::2] = half + np.arange(half)  # stred->von
    spawn_frames = int(nf * 0.18); cnt = 0
    canvas = np.zeros((H, W, 3), np.float64)
    rx, ry = _ring(cen, R, W, H)
    for f in range(nf):
        canvas *= 0.96
        if cnt < n:                                       # nabeh: 1 gulicka -> 3 -> viac a viac (zrychlene)
            if f < 9:
                target = 1
            elif f < 20:
                target = 3
            else:
                prog = min(1.0, (f - 20) / max(1, spawn_frames - 20))
                target = int(round(3 + (n - 3) * prog ** 2))
            target = min(target, n)
            if target > cnt:
                active[rel[cnt:target]] = True; cnt = target
        gy = g_high if f < grav_until else g_low
        for _ in range(2):
            vel[active, 1] += gy
            pos[active] += vel[active]
            d = pos - cen; dist = np.sqrt((d * d).sum(1))
            out = active & (dist > R)
            if out.any():
                nrm = d[out] / dist[out][:, None]
                vn = (vel[out] * nrm).sum(1)
                vel[out] -= 2.0 * vn[:, None] * nrm
                pos[out] = cen + nrm * (R - 0.5)
            x = pos[:, 0].astype(np.int32); y = pos[:, 1].astype(np.int32)
            ok = active & (x >= 0) & (x < W) & (y >= 0) & (y < H)
            np.add.at(canvas, (y[ok], x[ok]), col[ok] * 0.42)
        canvas[ry, rx] += np.array([0.05, 0.06, 0.09])
        yield _tonemap(canvas)


def particles_in_circle(W=1080, H=1920, fps=30, duration=18, n=5000, seed=7, **_kw):
    """Castice vychadzaju z vrchu, symetricky vejar nadol, odraza sa v kruhu -> symetricka siet."""
    cen = np.array([W / 2.0, H / 2.0])
    R = min(W, H) * 0.46
    pos = np.repeat(np.array([[cen[0], cen[1] - R * 0.97]]), n, axis=0).astype(np.float64)
    ang = np.linspace(-np.deg2rad(74), np.deg2rad(74), n) + np.pi / 2
    vel = np.stack([np.cos(ang), np.sin(ang)], 1) * (R * 0.011)
    col = _cool_warm(n)
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.95
        for _ in range(2):
            pos += vel
            d = pos - cen; dist = np.sqrt((d * d).sum(1))
            out = dist > R
            if out.any():
                nrm = d[out] / dist[out][:, None]
                vn = (vel[out] * nrm).sum(1)
                vel[out] -= 2 * vn[:, None] * nrm
                pos[out] = cen + nrm * (R - 0.5)
            x = pos[:, 0].astype(np.int32); y = pos[:, 1].astype(np.int32)
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            np.add.at(canvas, (y[ok], x[ok]), col[ok] * 0.45)
        yield _tonemap(canvas)


# ---------------------------------------------------------------- farebne schemy (variabilita)
def _scheme(n, name="cool_warm"):
    t = np.abs(np.linspace(-1, 1, n))
    if name == "ember":      # tepla: oranzova/zlta/cervena
        return np.clip(np.stack([1.0 - 0.10 * t, 0.42 - 0.28 * t, 0.10 + 0.04 * t], 1), 0.08, 1.0)
    if name == "ice":        # studena: cyan/modra/biela
        return np.clip(np.stack([0.28 + 0.55 * t, 0.66 - 0.08 * t, 1.0 - 0.28 * t], 1), 0.10, 1.0)
    if name == "neon":       # magenta/fialova/zelena
        return np.clip(np.stack([0.95 - 0.55 * t, 0.18 + 0.62 * t, 1.0 - 0.30 * t], 1), 0.08, 1.0)
    if name == "aurora":     # polarna ziara: zelena/tyrkys/fialova
        return np.clip(np.stack([0.25 + 0.50 * t, 0.95 - 0.35 * t, 0.50 + 0.42 * t], 1), 0.08, 1.0)
    if name == "sunset":     # zapad slnka: ruzova/oranzova/fialova
        return np.clip(np.stack([1.00 - 0.12 * t, 0.38 + 0.22 * t, 0.52 + 0.40 * t], 1), 0.08, 1.0)
    return _cool_warm(n)


SCHEMES = ["cool_warm", "ember", "ice", "neon", "aurora", "sunset"]


# ---------------------------------------------------------------- strange attractory (kazdy iny tvar)
def _attractor(deriv, dt, seed_state, proj=(0, 1), substeps=2, decay=0.965,
               intensity=0.32, sc_frac=0.40, settle=800, n=3800, spin_s=26.0, breath_s=11.0):
    """Vseobecny renderer pre 3D strange attractor: roj castic, TURNTABLE 3D rotacia (tvar sa
    stale toci) + jemne zoom-dychanie + hlbkove tienovanie (blizsie castice jasnejsie) -> zive 3D."""
    def sim(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="cool_warm", **_kw):
        rng = np.random.default_rng(seed)
        s = np.array(seed_state, dtype=np.float64)
        for _ in range(settle):
            s = s + deriv(s) * dt
        # castice startuju ako TESNY ZHLUK pri jednom bode -> chaos ich postupne rozkvitne do tvaru
        p = s + rng.uniform(-0.25, 0.25, (n, 3))
        col = _scheme(n, scheme)
        a0, a1 = proj
        a2 = ({0, 1, 2} - {a0, a1}).pop()                 # tretia os -> hlbka pre rotaciu
        ref = np.empty((4000, 3)); cur = s.copy()
        for i in range(4000):
            cur = cur + deriv(cur) * dt; ref[i] = cur
        c3 = (ref.min(0) + ref.max(0)) / 2.0              # 3D stred
        rxz = np.sqrt((ref[:, a0] - c3[a0]) ** 2 + (ref[:, a2] - c3[a2]) ** 2)
        # naklonena kamera (tilt ~22 stupnov): aj ked sa tvar otoci "hranou", stale vidno objem
        ct, st = 0.93, 0.37
        rad_y = ct * np.abs(ref[:, a1] - c3[a1]).max() + st * rxz.max()
        span = max(2 * rxz.max(), 2 * rad_y) + 1e-9
        sc0 = min(W, H) * sc_frac * 2.0 / span
        rad = rxz.max() + 1e-9
        cx, cy = W / 2.0, H / 2.0
        nf = int(fps * duration)
        active = np.zeros(n, bool); spawn = max(1, int(nf * 0.28)); cnt = 0
        canvas = np.zeros((H, W, 3), np.float64)
        for f in range(nf):
            canvas *= decay
            if cnt < n:        # nabeh: castice sa postupne objavuju (od 1 -> vsetky) = viditelny start
                target = n if f >= spawn else min(n, max(cnt + 1, int(n * (f / spawn) ** 1.4)))
                active[cnt:target] = True; cnt = target
            th = np.deg2rad(52) * np.sin(2 * np.pi * f / (fps * spin_s))  # KOLISANIE (rock), nie plna
            th += np.deg2rad(18)                          # +offset -> nikdy presne "na hranu" (ploche atraktory)
            co, si = np.cos(th), np.sin(th)
            sc = sc0 * (1.0 + 0.06 * np.sin(2 * np.pi * f / (fps * breath_s)))  # jemne dychanie
            for _ in range(substeps):
                p[active] = p[active] + deriv(p[active]) * dt
                px = p[active, a0] - c3[a0]; pz = p[active, a2] - c3[a2]
                X = px * co + pz * si                     # rotovana projekcia
                Zr = -px * si + pz * co                   # hlbkova os po rotacii
                Zd = Zr / rad                             # -1..1 (blizsie = jasnejsie)
                sx = (cx + X * sc).astype(np.int32)
                sy = (cy + ((p[active, a1] - c3[a1]) * ct + Zr * st) * sc).astype(np.int32)
                ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
                w = (0.72 + 0.38 * np.clip(Zd, -1, 1))[:, None]   # hlbkove tienovanie
                cc = col[active] * w
                np.add.at(canvas, (sy[ok], sx[ok]), cc[ok] * intensity)
            yield _tonemap(canvas)
    return sim


def _d_lorenz(s):
    sig, rho, beta = 10.0, 28.0, 8.0 / 3.0
    x, y, z = s[..., 0], s[..., 1], s[..., 2]
    return np.stack([sig * (y - x), x * (rho - z) - y, x * y - beta * z], axis=-1)


def _d_aizawa(s):
    x, y, z = s[..., 0], s[..., 1], s[..., 2]
    a, b, c, d, e, ff = 0.95, 0.7, 0.6, 3.5, 0.25, 0.1
    return np.stack([(z - b) * x - d * y, d * x + (z - b) * y,
                     c + a * z - z**3 / 3.0 - (x * x + y * y) * (1 + e * z) + ff * z * x**3], axis=-1)


def _d_thomas(s):
    b = 0.208; x, y, z = s[..., 0], s[..., 1], s[..., 2]
    return np.stack([np.sin(y) - b * x, np.sin(z) - b * y, np.sin(x) - b * z], axis=-1)


def _d_halvorsen(s):
    a = 1.89; x, y, z = s[..., 0], s[..., 1], s[..., 2]
    return np.stack([-a * x - 4 * y - 4 * z - y * y, -a * y - 4 * z - 4 * x - z * z,
                     -a * z - 4 * x - 4 * y - x * x], axis=-1)


def _d_rossler(s):
    a, b, c = 0.2, 0.2, 5.7; x, y, z = s[..., 0], s[..., 1], s[..., 2]
    return np.stack([-(y + z), x + a * y, b + z * (x - c)], axis=-1)


# lorenz_swarm = Lorenzov motyl, teraz s 3D rotaciou (meno ostava kvoli starym specom v banke)
lorenz_swarm = _attractor(_d_lorenz, 0.005, [0.1, 0.1, 25.0], proj=(0, 2), settle=900, sc_frac=0.40, intensity=0.30)
aizawa_attractor = _attractor(_d_aizawa, 0.01, [0.1, 0.0, 0.0], proj=(0, 2), settle=1200, sc_frac=0.40, intensity=0.34)
thomas_attractor = _attractor(_d_thomas, 0.06, [0.1, 0.12, 0.08], proj=(0, 1), settle=600, sc_frac=0.42, intensity=0.30, decay=0.97)
halvorsen_attractor = _attractor(_d_halvorsen, 0.0065, [-1.48, -1.51, 2.04], proj=(0, 1), settle=900, substeps=3, sc_frac=0.40, intensity=0.30)
rossler_attractor = _attractor(_d_rossler, 0.03, [0.1, 0.1, 0.1], proj=(0, 1), settle=900, sc_frac=0.40, intensity=0.30, decay=0.97)


# ---------------------------------------------------------------- flow field (plynule prudy castic)
def flow_field(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="ice", n=16000, **_kw):
    """Castice tecu pozdlz hladkeho silopolia -> ziarive prudy/ribbons (uplne iny vzhlad).
    Dlhsie stopy (mensi decay) + vela castic -> husta sietova struktura prudov."""
    rng = np.random.default_rng(seed)
    pos = np.stack([rng.uniform(0, W, n), rng.uniform(0, H, n)], 1)
    ang0 = rng.uniform(0, 2 * np.pi)
    col = _scheme(n, scheme)
    canvas = np.zeros((H, W, 3), np.float64)
    sc = 2.6 / min(W, H); spd = min(W, H) * 0.0030
    for f in range(int(fps * duration)):
        canvas *= 0.968
        tt = ang0 + f * 0.010
        for _ in range(2):
            xx, yy = pos[:, 0] * sc, pos[:, 1] * sc
            a = (np.sin(xx * 1.2 + tt) + np.cos(yy * 1.2 - tt * 0.7) + 0.6 * np.sin((xx + yy) * 0.6 + tt)) * np.pi
            pos[:, 0] = (pos[:, 0] + np.cos(a) * spd) % W
            pos[:, 1] = (pos[:, 1] + np.sin(a) * spd) % H
            x = pos[:, 0].astype(np.int32); y = pos[:, 1].astype(np.int32)
            np.add.at(canvas, (y, x), col * 0.16)
        yield _tonemap(canvas, exposure=1.35)


# ---------------------------------------------------------------- NOVE SIMULACIE (upgrade)
def double_pendulum(W=1080, H=1920, fps=30, duration=18, n=700, seed=7, scheme="cool_warm", **_kw):
    """BUTTERFLY EFFECT nazivo: stovky dvojitych kyvadiel s TAKMER rovnakym startom (rozdiel
    0.0001 stupna). Prvych par sekund sa hybu ako jedno -> potom sa rozdelia do dahoveho vejara.
    Najlepsia vizualizacia chaosu aka existuje."""
    rng = np.random.default_rng(seed)
    g, L1, L2, m1, m2 = 9.81, 1.0, 1.0, 1.0, 1.0
    th1 = np.full(n, 2.094) + np.linspace(0, 1, n) * 1e-4     # ~120 stupnov + mikroskopicky rozdiel
    th2 = np.full(n, 2.094) + rng.uniform(-1e-6, 1e-6, n)
    w1 = np.zeros(n); w2 = np.zeros(n)
    col = _scheme(n, scheme)
    px0, py0 = W / 2.0, H * 0.40
    sc = min(W, H) * 0.215
    dt = 1.0 / (fps * 3)
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.94
        for _ in range(3):
            d = th1 - th2
            den = 2 * m1 + m2 - m2 * np.cos(2 * d)
            a1 = (-g * (2 * m1 + m2) * np.sin(th1) - m2 * g * np.sin(th1 - 2 * th2)
                  - 2 * np.sin(d) * m2 * (w2 * w2 * L2 + w1 * w1 * L1 * np.cos(d))) / (L1 * den)
            a2 = (2 * np.sin(d) * (w1 * w1 * L1 * (m1 + m2) + g * (m1 + m2) * np.cos(th1)
                  + w2 * w2 * L2 * m2 * np.cos(d))) / (L2 * den)
            w1 = np.clip(w1 + a1 * dt, -25, 25); w2 = np.clip(w2 + a2 * dt, -25, 25)
            th1 += w1 * dt; th2 += w2 * dt
            x1 = px0 + np.sin(th1) * L1 * sc; y1 = py0 + np.cos(th1) * L1 * sc
            x2 = x1 + np.sin(th2) * L2 * sc; y2 = y1 + np.cos(th2) * L2 * sc
            xi = x2.astype(np.int32); yi = y2.astype(np.int32)
            ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
            np.add.at(canvas, (yi[ok], xi[ok]), col[ok] * 0.62)        # koncovy bod jasny
            xj = x1.astype(np.int32); yj = y1.astype(np.int32)
            ok1 = (xj >= 0) & (xj < W) & (yj >= 0) & (yj < H)
            np.add.at(canvas, (yj[ok1], xj[ok1]), col[ok1] * 0.10)     # kib jemne
        canvas[int(py0) - 2:int(py0) + 3, int(px0) - 2:int(px0) + 3] += 0.6   # pivot bodka
        yield _tonemap(canvas)


def clifford_morph(W=1080, H=1920, fps=30, duration=18, n=9000, seed=7, scheme="neon", **_kw):
    """Cliffordov atraktor co sa MORFUJE: parametre sa pomaly vlnia -> organicky atramentovy
    tvar sa cely cas preliewa do novych foriem (nikdy nestoji). Uplne iny vzhlad nez roje bodiek."""
    rng = np.random.default_rng(seed)
    a0, b0, c0, d0 = -1.4, 1.6, 1.0, 0.7
    x = rng.uniform(-1, 1, n); y = rng.uniform(-1, 1, n)
    col = _scheme(n, scheme)
    cx, cy = W / 2.0, H / 2.0
    sc = min(W, H) * 0.44 / 2.05
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.90
        at = a0 + 0.16 * np.sin(2 * np.pi * f / (fps * 17.0))       # pomale morfovanie tvaru
        dt_ = d0 + 0.14 * np.cos(2 * np.pi * f / (fps * 12.0))
        for _ in range(3):
            xn = np.sin(at * y) + c0 * np.cos(at * x)
            y = np.sin(b0 * x) + dt_ * np.cos(b0 * y)
            x = xn
            sx = (cx + x * sc).astype(np.int32)
            sy = (cy + y * sc * 1.35).astype(np.int32)               # vertikalne roztiahnute (9:16)
            ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
            np.add.at(canvas, (sy[ok], sx[ok]), col[ok] * 0.22)
        yield _tonemap(canvas)


def galaxy_spiral(W=1080, H=1920, fps=30, duration=18, n=15000, seed=7, scheme="ice", **_kw):
    """Rotujuca galaxia: disk hviezd s diferencialnou rotaciou (vnutro rychlejsie) -> spiralove
    ramena sa naturalne stacaju. Teple jadro, chladne okraje, stale v pohybe."""
    rng = np.random.default_rng(seed)
    R = min(W, H) * 0.47
    r = R * np.sqrt(rng.uniform(0.015, 1.0, n))
    th = rng.uniform(0, 2 * np.pi, n)
    th += 0.55 * np.sin(2 * th + r / R * 3.0)                        # 2-ramenna nehomogenita
    tnorm = np.clip(r / R, 0, 1)
    base = _scheme(n, scheme)
    warm = np.array([1.0, 0.75, 0.45])
    col = warm[None, :] * (1 - tnorm[:, None]) ** 1.5 * 0.9 + base * (0.35 + 0.65 * tnorm[:, None])
    w0 = 0.062                                                       # uhlova rychlost jadra (rad/frame)
    om = w0 * (R * 0.16) / (r + R * 0.16)                            # plocha rotacna krivka
    cx, cy = W / 2.0, H / 2.0
    tilt = 0.60                                                      # naklon disku (elipsa)
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.90
        for _ in range(2):
            th += om * 0.5
            x = (cx + r * np.cos(th)).astype(np.int32)
            y = (cy + r * np.sin(th) * tilt).astype(np.int32)
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            np.add.at(canvas, (y[ok], x[ok]), col[ok] * 0.28)
        yy, xx = int(cy), int(cx)
        canvas[yy - 3:yy + 4, xx - 3:xx + 4] += np.array([0.5, 0.38, 0.22])   # ziarive jadro
        yield _tonemap(canvas)


def weaving_pens(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="cool_warm", **_kw):
    """Jedno alebo viac 'pier' kresli plynule NAHODNE krivky (superpozicia kruhov = epicykle/Fourier)
    co sa PREPLIETAJU do nahodnych obrazcov. Kazde pero ma vlastne nahodne kruhy (radius/rychlost/faza)
    -> iny tvar; dlha perzistencia -> obrazec sa postupne 'nakresli' a stale sa jemne pretvara."""
    rng = np.random.default_rng(seed)
    n_pens = int(rng.integers(2, 5))                    # 2-4 pier ('jedna alebo viacej')
    cen = np.array([W / 2.0, H / 2.0])
    Sc = min(W, H) * 0.40
    cols = _scheme(max(3, n_pens), scheme)[:n_pens]     # kazde pero ina farba
    pens = []
    for _ in range(n_pens):
        K = int(rng.integers(3, 6))                     # 3-5 kruhov = zlozitost tvaru
        w = rng.integers(1, 6, K).astype(float) * rng.choice([-1.0, 1.0], K)  # celociselne -> uzatvorene krivky
        w += rng.uniform(-0.03, 0.03, K)                # mikro-odchylka -> tvar sa pomaly pretvara (nikdy nezastane)
        r = rng.uniform(0.2, 1.0, K); r /= r.sum()      # radiusy (normalizovane, sum=1)
        p = rng.uniform(0, 2 * np.pi, K)
        pens.append((w, r, p))
    canvas = np.zeros((H, W, 3), np.float64)
    speed = 2 * np.pi / (fps * 6.0)                     # ~6s na zakladny obeh

    def pos(pen, t):
        w, r, p = pen
        ang = w * t + p
        return cen[0] + Sc * float(np.sum(r * np.cos(ang))), cen[1] + Sc * float(np.sum(r * np.sin(ang)))

    prev = [None] * n_pens
    nf = int(fps * duration)
    # ofsety pre hrubsiu (2px) ziarivu ciaru
    OFF = np.array([[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]])
    for f in range(nf):
        canvas *= 0.9925                                # dlha perzistencia -> obrazec sa 'nakresli'
        for sub in range(6):                            # 6 substepov = hladka ciara
            t = (f + sub / 6.0) * speed
            for i, pen in enumerate(pens):
                x, y = pos(pen, t)
                if prev[i] is not None:
                    x0, y0 = prev[i]
                    steps = int(max(2, min(64, np.hypot(x - x0, y - y0))))
                    xs = np.linspace(x0, x, steps); ys = np.linspace(y0, y, steps)
                    for dx, dy in OFF:
                        xi = (xs + dx).astype(np.int32); yi = (ys + dy).astype(np.int32)
                        ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
                        w = 0.42 if (dx or dy) else 0.62         # jadro jasnejsie, okraj slabsie
                        np.add.at(canvas, (yi[ok], xi[ok]), cols[i] * w)
                prev[i] = (x, y)
        yield _tonemap(canvas, exposure=1.5, bloom=3.2)


_OFF = np.array([[0, 0], [1, 0], [0, 1], [-1, 0], [0, -1]])


def _draw_seg(canvas, x0, y0, x1, y1, W, H, color):
    """Hruba (2px) ziariva ciara medzi dvoma bodmi (aditivne do canvasu)."""
    steps = int(max(2, min(70, np.hypot(x1 - x0, y1 - y0))))
    xs = np.linspace(x0, x1, steps); ys = np.linspace(y0, y1, steps)
    for dx, dy in _OFF:
        xi = (xs + dx).astype(np.int32); yi = (ys + dy).astype(np.int32)
        ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
        w = 0.62 if not (dx or dy) else 0.42
        np.add.at(canvas, (yi[ok], xi[ok]), color * w)


def spirograph(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="neon", **_kw):
    """Perá kreslia SYMETRICKE rozety (hypotrochoidy s nahodnymi prevodmi) co sa preplietaju.
    Kazde pero iny prevod -> iny pocet listkov; jemna precesia -> stale sa dotvara."""
    rng = np.random.default_rng(seed)
    n_pens = int(rng.integers(2, 4))
    cen = np.array([W / 2.0, H / 2.0]); cols = _scheme(max(3, n_pens), scheme)[:n_pens]
    from math import gcd
    pens = []
    for _ in range(n_pens):
        Rr = int(rng.integers(7, 13)); rr = int(rng.integers(2, Rr - 1))
        while gcd(Rr, rr) != 1:                             # NESUDELITELNE -> max listkov = vzdy bohata rozeta
            rr = int(rng.integers(2, Rr - 1))
        k = (Rr - rr) / rr + rng.uniform(-0.015, 0.015)     # jemna odchylka -> precesia
        d = rng.uniform(0.55, 1.25)
        amp = (Rr - rr) + d * rr
        pens.append((Rr - rr, rr, k, d, rng.uniform(0, 2 * np.pi), amp))
    Sc = min(W, H) * 0.44 / (max(p[5] for p in pens) + 1e-9)
    canvas = np.zeros((H, W, 3), np.float64)
    speed = 2 * np.pi / (fps * 3.2); prev = [None] * n_pens   # rychlejsie -> rozeta sa cela dokresli
    for f in range(int(fps * duration)):
        canvas *= 0.9945
        for sub in range(6):
            t = (f + sub / 6.0) * speed
            for i, (Rr, rr, k, d, ph, _amp) in enumerate(pens):
                x = cen[0] + Sc * (Rr * np.cos(t + ph) + d * rr * np.cos(k * t + ph))
                y = cen[1] + Sc * (Rr * np.sin(t + ph) - d * rr * np.sin(k * t + ph))
                if prev[i] is not None:
                    _draw_seg(canvas, prev[i][0], prev[i][1], x, y, W, H, cols[i])
                prev[i] = (x, y)
        yield _tonemap(canvas, exposure=1.5, bloom=3.2)


def harmonograph(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="ember", **_kw):
    """Kyvadlove pero: sucet 2 tlmenych sinusoid na kazdu os -> organicka rozeta co sa
    postupne 'nakresli' a jemne dosadne. Nahodne frekvencie -> vzdy iny tvar."""
    rng = np.random.default_rng(seed)
    n_pens = int(rng.integers(1, 3))                        # 1-2 kyvadla
    cen = np.array([W / 2.0, H / 2.0]); cols = _scheme(max(3, n_pens), scheme)[:n_pens]
    Sc = min(W, H) * 0.40
    pens = []
    for _ in range(n_pens):
        base = rng.uniform(1.6, 3.2)
        fx = np.array([base, base + rng.choice([-2, -1, 1, 2]) + rng.uniform(-0.02, 0.02)])
        fy = np.array([base + rng.uniform(-0.02, 0.02), base + rng.choice([-2, -1, 1, 2]) + rng.uniform(-0.02, 0.02)])
        px = rng.uniform(0, 2 * np.pi, 2); py = rng.uniform(0, 2 * np.pi, 2)
        dmp = rng.uniform(0.010, 0.020)
        pens.append((fx, fy, px, py, dmp))
    canvas = np.zeros((H, W, 3), np.float64)
    speed = 2 * np.pi / (fps * 2.0); prev = [None] * n_pens
    for f in range(int(fps * duration)):
        canvas *= 0.9945
        for sub in range(6):
            t = (f + sub / 6.0) * speed
            for i, (fx, fy, px, py, dmp) in enumerate(pens):
                e = np.exp(-dmp * t)
                x = cen[0] + Sc * 0.5 * e * np.sum(np.sin(fx * t + px))
                y = cen[1] + Sc * 0.5 * e * np.sum(np.sin(fy * t + py))
                if prev[i] is not None:
                    _draw_seg(canvas, prev[i][0], prev[i][1], x, y, W, H, cols[i])
                prev[i] = (x, y)
        yield _tonemap(canvas, exposure=1.5, bloom=3.2)


def wander_ribbons(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="aurora", **_kw):
    """Perá NAHODNE bludia (hladke plynule zatacanie) a nechavaju preplietene ziarive stuhy.
    Uplne nahodne cesty (nie periodicke) -> zakazdym iny organicky obrazec."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(3, 6))                             # 3-5 stuh (hustejsie preplietanie)
    cols = _scheme(max(3, n), scheme)[:n]
    pos = np.stack([rng.uniform(W * 0.35, W * 0.65, n), rng.uniform(H * 0.4, H * 0.6, n)], 1)
    ang = rng.uniform(0, 2 * np.pi, n)
    fx = rng.uniform(1.5, 3.0, n); fy = rng.uniform(1.5, 3.0, n); ph = rng.uniform(0, 6.28, n)
    spd = min(W, H) * 0.0058; fld = 2.4 / min(W, H)
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.9915                                    # dlhsia perzistencia -> hustejsie stuhy
        for sub in range(4):
            t = (f + sub / 4.0) / fps
            xx = pos[:, 0] * fld; yy = pos[:, 1] * fld
            turn = 0.16 * (np.sin(xx * fx + t * 0.7 + ph) + np.cos(yy * fy - t * 0.5))
            ang = ang + turn + rng.uniform(-0.04, 0.04, n)   # hladke zatacanie + stipka nahody
            nx = pos[:, 0] + np.cos(ang) * spd; ny = pos[:, 1] + np.sin(ang) * spd
            # odraz od okrajov (drz stuhy v ramci)
            hit = (nx < 6) | (nx > W - 6); ang = np.where(hit, np.pi - ang, ang)
            hit2 = (ny < 6) | (ny > H - 6); ang = np.where(hit2, -ang, ang)
            nx = np.clip(nx, 6, W - 6); ny = np.clip(ny, 6, H - 6)
            for i in range(n):
                _draw_seg(canvas, pos[i, 0], pos[i, 1], nx[i], ny[i], W, H, cols[i])
            pos[:, 0] = nx; pos[:, 1] = ny
        yield _tonemap(canvas, exposure=1.4, bloom=3.0)


SIMS = {
    "stream_sphere": stream_sphere,
    "weaving_pens": weaving_pens,
    "spirograph": spirograph,
    "harmonograph": harmonograph,
    "wander_ribbons": wander_ribbons,
    "particles_in_circle": particles_in_circle,
    "lorenz_swarm": lorenz_swarm,
    "aizawa_attractor": aizawa_attractor,
    "thomas_attractor": thomas_attractor,
    "halvorsen_attractor": halvorsen_attractor,
    "rossler_attractor": rossler_attractor,
    "flow_field": flow_field,
    "double_pendulum": double_pendulum,
    "clifford_morph": clifford_morph,
    "galaxy_spiral": galaxy_spiral,
}
