# -*- coding: utf-8 -*-
"""Entropy - hypnoticke fyzikalne/matematicke simulacie renderovane na cierno so ziarivymi stopami.
Kazda sim je generator co yielduje uint8 RGB framy (H x W x 3): aditivny canvas + decay = ziarive
stopy, lahky bloom cez PIL (glow). Klucom ku krase je KOHERENTNY symetricky pohyb (vlny, nie sum)."""
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


def lorenz_swarm(W=1080, H=1920, fps=30, duration=18, n=4000, seed=3, **_kw):
    """Lorenzov atraktor: roj castic z jedneho bodu sa rozvinie do slavneho 'motyla' chaosu.
    Klasicky priklad ako z jednoduchych pravidiel vznika nekonecna nepredvidatelnost."""
    rng = np.random.default_rng(seed)
    sig, rho, beta = 10.0, 28.0, 8.0 / 3.0
    dt = 0.005
    # naseeduj castice po CELOM atraktore (jedna trajektoria -> rozlozenie) = hned cely motyl
    s = np.array([0.1, 0.1, 25.0]); pts = np.empty((n, 3))
    for _ in range(800):
        x, y, z = s; s = s + np.array([sig * (y - x), x * (rho - z) - y, x * y - beta * z]) * dt
    for i in range(n):
        for _ in range(3):
            x, y, z = s; s = s + np.array([sig * (y - x), x * (rho - z) - y, x * y - beta * z]) * dt
        pts[i] = s
    p = pts + rng.uniform(-0.02, 0.02, (n, 3))
    col = _cool_warm(n)
    cx, cy = W / 2.0, H / 2.0
    sc = min(W, H) * 0.017
    canvas = np.zeros((H, W, 3), np.float64)
    for f in range(int(fps * duration)):
        canvas *= 0.965
        for _ in range(2):
            x, y, z = p[:, 0].copy(), p[:, 1].copy(), p[:, 2].copy()
            p[:, 0] += sig * (y - x) * dt
            p[:, 1] += (x * (rho - z) - y) * dt
            p[:, 2] += (x * y - beta * z) * dt
            sx = (cx + p[:, 0] * sc).astype(np.int32)
            sy = (cy + (p[:, 2] - 25.0) * sc).astype(np.int32)
            ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
            np.add.at(canvas, (sy[ok], sx[ok]), col[ok] * 0.32)
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
    return _cool_warm(n)


SCHEMES = ["cool_warm", "ember", "ice", "neon"]


# ---------------------------------------------------------------- strange attractory (kazdy iny tvar)
def _attractor(deriv, dt, seed_state, proj=(0, 1), substeps=2, decay=0.965,
               intensity=0.32, sc_frac=0.40, settle=800, n=3800):
    """Vseobecny renderer pre 3D strange attractor: roj castic, projekcia do 2D, auto-fit do ramca."""
    def sim(W=1080, H=1920, fps=30, duration=18, seed=7, scheme="cool_warm", **_kw):
        rng = np.random.default_rng(seed)
        s = np.array(seed_state, dtype=np.float64)
        for _ in range(settle):
            s = s + deriv(s) * dt
        # castice startuju ako TESNY ZHLUK pri jednom bode -> chaos ich postupne rozkvitne do tvaru
        # (jasny ZACIATOK: bod sa objavi a rozvinie do atraktora) + postupny nabeh poctu castic
        p = s + rng.uniform(-0.25, 0.25, (n, 3))
        col = _scheme(n, scheme)
        a0, a1 = proj
        ref = np.empty((4000, 3)); cur = s.copy()
        for i in range(4000):
            cur = cur + deriv(cur) * dt; ref[i] = cur
        rx, ry = ref[:, a0], ref[:, a1]
        cx0 = (rx.min() + rx.max()) / 2.0; cy0 = (ry.min() + ry.max()) / 2.0
        span = max(rx.max() - rx.min(), ry.max() - ry.min()) + 1e-9
        sc = min(W, H) * sc_frac * 2.0 / span
        cx, cy = W / 2.0, H / 2.0
        nf = int(fps * duration)
        active = np.zeros(n, bool); spawn = max(1, int(nf * 0.28)); cnt = 0
        canvas = np.zeros((H, W, 3), np.float64)
        for f in range(nf):
            canvas *= decay
            if cnt < n:        # nabeh: castice sa postupne objavuju (od 1 -> vsetky) = viditelny start
                target = n if f >= spawn else min(n, max(cnt + 1, int(n * (f / spawn) ** 1.4)))
                active[cnt:target] = True; cnt = target
            for _ in range(substeps):
                p[active] = p[active] + deriv(p[active]) * dt
                sx = (cx + (p[active, a0] - cx0) * sc).astype(np.int32)
                sy = (cy + (p[active, a1] - cy0) * sc).astype(np.int32)
                ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
                cc = col[active]
                np.add.at(canvas, (sy[ok], sx[ok]), cc[ok] * intensity)
            yield _tonemap(canvas)
    return sim


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


SIMS = {
    "stream_sphere": stream_sphere,
    "particles_in_circle": particles_in_circle,
    "lorenz_swarm": lorenz_swarm,
    "aizawa_attractor": aizawa_attractor,
    "thomas_attractor": thomas_attractor,
    "halvorsen_attractor": halvorsen_attractor,
    "rossler_attractor": rossler_attractor,
    "flow_field": flow_field,
}
