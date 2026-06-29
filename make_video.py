#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entropy render: simulacia -> mp4 (1080x1920) + text na obrazovke + atmosfericka hudba s fade in/out.
Ciste graficke video: konstantny fps, raw frames -> libx264 (crf 19, strop bitrate), yuv420p. Ziadne seky."""
import json, os, random, re, subprocess, sys
import numpy as np
import appconfig
import simulations as S
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))


def _slug(t):
    return re.sub(r"[^a-z0-9]+", "_", (t or "").lower()).strip("_")[:50] or "sim"


def _font(size):
    for p in (r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", r"C:\Windows\Fonts\Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _text_overlay(W, H, text):
    """staticky biely text hore (zalomeny, centrovany) ako RGB overlay (cierne pozadie)."""
    ov = np.zeros((H, W, 3), np.uint8)
    text = (text or "").strip()
    if not text:
        return ov
    img = Image.new("RGB", (W, H), (0, 0, 0)); d = ImageDraw.Draw(img)
    font = _font(int(W * 0.055))
    maxw = W * 0.86
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    y = int(H * 0.085)
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(245, 245, 245))
        y += int(getattr(font, "size", int(W * 0.055)) * 1.28)
    return np.asarray(img, np.uint8)


def main(spec_path):
    cfg = appconfig.load()
    spec = json.load(open(spec_path, encoding="utf-8")) if spec_path else {}
    sim = spec.get("sim", "stream_sphere")
    if sim not in S.SIMS:
        print(f"[pozn.] neznama sim '{sim}', pouzijem stream_sphere"); sim = "stream_sphere"
    W, H, fps = int(cfg["width"]), int(cfg["height"]), int(cfg["fps"])
    dur = float(cfg.get("duration", 18))
    ff = cfg["ffmpeg"]
    out_dir = os.path.join(ROOT, "output"); os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(ROOT, "temp"); os.makedirs(tmp, exist_ok=True)
    title = spec.get("title") or sim
    slug = _slug(title)
    silent = os.path.join(tmp, slug + "_silent.mp4")

    overlay = _text_overlay(W, H, spec.get("onscreen", ""))
    has_txt = overlay.any()

    # 1) raw RGB frames (+ text overlay) -> ffmpeg -> ciste mp4
    cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-maxrate", "5M", "-bufsize", "10M", "-pix_fmt", "yuv420p", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    try:
        for frame in S.SIMS[sim](W=W, H=H, fps=fps, duration=dur, seed=int(spec.get("seed", 7))):
            if has_txt:
                frame = np.maximum(frame, overlay)
            p.stdin.write(frame.tobytes()); n += 1
    finally:
        p.stdin.close()
    if p.wait() != 0:
        print("CHYBA: ffmpeg render zlyhal"); sys.exit(1)
    print(f"  vyrenderovanych {n} framov ({n/fps:.1f}s) -> {os.path.basename(silent)}")

    # 2) hudba: loop + loudnorm -14 LUFS + fade in/out + orez na dlzku videa
    out = os.path.join(out_dir, slug + ".mp4")
    mdir = os.path.join(ROOT, "assets", "music")
    musics = [os.path.join(mdir, m) for m in os.listdir(mdir)
              if m.lower().endswith((".mp3", ".m4a", ".wav"))] if os.path.isdir(mdir) else []
    if musics:
        vol = cfg.get("music_volume", 1.0)
        fade = float(cfg.get("audio_fade", 1.8))
        fo = max(0.1, dur - fade)
        af = (f"volume={vol},loudnorm=I=-14:TP=-1.5:LRA=11,"
              f"afade=t=in:st=0:d={fade},afade=t=out:st={fo:.2f}:d={fade}")
        track = random.choice(musics)                 # nahodny track -> variabilita hudby
        r = subprocess.run([ff, "-y", "-i", silent, "-stream_loop", "-1", "-i", track,
                            "-c:v", "copy", "-map", "0:v", "-map", "1:a",
                            "-af", af, "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-shortest", out])
        if r.returncode != 0:
            os.replace(silent, out)
    else:
        os.replace(silent, out)
    print(f"  HOTOVO -> {out}")

    # 3) .txt (titulok + popis + hashtagy + credit)
    desc = (spec.get("description") or "").strip()
    tags = " ".join(spec.get("hashtags", []))
    credit = cfg.get("music_credit", "")
    body = "\n".join(x for x in [title, "", desc, "", tags, "", credit] if x != "")
    open(out[:-4] + ".txt", "w", encoding="utf-8").write(body)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
