#!/usr/bin/env python3
"""
Nahra hotove videa z output/ PRIAMO na YouTube (Data API + OAuth) ako Shorts,
naplanovane na 08:00/15:00/20:00 Bratislava cez status.publishAt.
ZIADEN Buffer ani Cloudinary. Stav v uploaded.json (ziadne duplicity).

Pouzitie:  python push_to_youtube.py [pocet]   (default 3)
Potrebuje (config.json alebo ENV): youtube_client_id, youtube_client_secret, youtube_refresh_token
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys

import requests

import appconfig

ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADED = os.path.join(ROOT, "uploaded.json")
OUT = os.path.join(ROOT, "output")
SLOT_HOURS = [8, 15, 20]
CATEGORY = "24"   # Entertainment (EyeHeist puzzle kanal)


def next_slots(n):
    """n najblizsich buducich casov 08/15/20 (Bratislava) ako ISO UTC."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Bratislava")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=2))
    now = datetime.datetime.now(tz)
    out, day = [], 0
    while len(out) < n:
        for h in SLOT_HOURS:
            t = (now + datetime.timedelta(days=day)).replace(hour=h, minute=0, second=0, microsecond=0)
            if t > now:
                out.append(t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
                if len(out) >= n:
                    break
        day += 1
    return out


def load_uploaded():
    if os.path.exists(UPLOADED):
        try:
            return json.load(open(UPLOADED, encoding="utf-8"))
        except Exception:
            return []
    return []


def save_uploaded(u):
    json.dump(u, open(UPLOADED, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def access_token(cid, csec, rtok):
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": cid, "client_secret": csec, "refresh_token": rtok,
        "grant_type": "refresh_token"})
    r.raise_for_status()
    return r.json()["access_token"]


def read_meta(txt):
    """Z .txt vedla videa: title = 1. neprazdny riadok; desc = zvysok; tags = #slova."""
    if not os.path.exists(txt):
        return "Entropy", "", []
    lines = open(txt, encoding="utf-8").read().split("\n")
    title = next((l.strip() for l in lines if l.strip()), "Entropy")
    body = "\n".join(lines[1:]).strip()
    tags = [w[1:] for w in body.split() if w.startswith("#")][:15]
    return title, body, tags


def _ffmpeg():
    """Cesta k ffmpeg: PATH (GitHub runner) alebo lokalny imageio-ffmpeg."""
    c = shutil.which("ffmpeg")
    if c:
        return c
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def pick_clean_frame(mp4, out_jpg, scan_frac=0.25):
    """Vyberie frame BEZ vypaleneho titulku z prvej casti videa (dalej byva riesenie
    = spoiler). Skoruje podiel skoro-bielych pixelov v titulkovom pase, kandidata potom
    vytiahne v plnom rozliseni PRESNYM seekom a cistotu este raz overi. Vrati True/False."""
    ff = _ffmpeg()
    if not ff:
        return False
    try:
        from PIL import Image
    except Exception:
        return False
    tmp = tempfile.mkdtemp(prefix="thumb_")
    try:
        pr = subprocess.run([ff, "-i", mp4], capture_output=True, text=True, timeout=120)
        m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", pr.stderr or "")
        dur = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 0.0
        scan = max(5.0, dur * scan_frac) if dur else 8.0
        subprocess.run([ff, "-y", "-t", "%.2f" % scan, "-i", mp4, "-vf", "fps=2,scale=270:-1",
                        "-q:v", "4", os.path.join(tmp, "f_%04d.jpg")], capture_output=True, timeout=300)

        def caption_ratio(img):
            g = img.convert("L")
            w, h = g.size
            px = g.crop((0, int(h * 0.72), w, int(h * 0.92))).tobytes()
            return sum(1 for v in px if v > 235) / float(len(px))

        cands = []
        for f in sorted(os.listdir(tmp)):
            if not f.endswith(".jpg"):
                continue
            idx = int(f[2:6])
            if idx < 4:                      # prve ~2 s preskoc (nabeh)
                continue
            cands.append((caption_ratio(Image.open(os.path.join(tmp, f))), idx))
        cands.sort()
        for score, idx in cands[:6]:
            ts = idx / 2.0
            r = subprocess.run([ff, "-y", "-i", mp4, "-ss", "%.2f" % ts, "-frames:v", "1",
                                "-q:v", "2", out_jpg], capture_output=True, timeout=180)
            if r.returncode != 0 or not os.path.exists(out_jpg) or os.path.getsize(out_jpg) < 5000:
                continue
            if caption_ratio(Image.open(out_jpg)) <= 0.0015:
                print("    thumbnail: cisty frame @%.1fs" % ts)
                return True
        if os.path.exists(out_jpg):
            os.remove(out_jpg)
        return False
    except Exception as e:
        print("    thumbnail: vyber framu zlyhal (nekriticke): " + str(e)[:120])
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def set_thumbnail(tok, video_id, jpg):
    """thumbnails.set (scope youtube.upload staci). 403 = kanal nema zapnute custom thumbnails."""
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=" + video_id,
        headers={"Authorization": "Bearer " + tok, "Content-Type": "image/jpeg"},
        data=open(jpg, "rb").read(), timeout=120)
    if r.status_code == 403:
        print("    thumbnail 403: zapni custom thumbnails na kanali (overenie telefonom)")
        return False
    r.raise_for_status()
    return True


def upload(tok, mp4, title, desc, tags, publish_at):
    if "#Shorts" not in title and "#shorts" not in title and len(title) < 92:
        title = title + " #Shorts"
    if "#shorts" not in desc.lower():
        desc = (desc + "\n#Shorts").strip()
    meta = {
        "snippet": {"title": title[:100], "description": desc[:4900],
                    "tags": tags, "categoryId": CATEGORY},
        "status": {"privacyStatus": "private", "publishAt": publish_at,
                   "selfDeclaredMadeForKids": False},
    }
    init = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/*"},
        data=json.dumps(meta).encode("utf-8"), timeout=60)
    init.raise_for_status()
    up_url = init.headers["Location"]
    with open(mp4, "rb") as f:
        body = f.read()
    put = requests.put(up_url, headers={"Content-Type": "video/*", "Content-Length": str(len(body))},
                       data=body, timeout=900)
    put.raise_for_status()
    return put.json().get("id")


def main():
    nums = [a for a in sys.argv[1:] if a.isdigit()]
    n = int(nums[0]) if nums else 3
    cfg = appconfig.load()
    cid = cfg.get("youtube_client_id")
    csec = cfg.get("youtube_client_secret")
    rtok = cfg.get("youtube_refresh_token")
    if not (cid and csec and rtok):
        print("CHYBA: chybaju YouTube OAuth udaje (client_id/secret/refresh_token).")
        return
    uploaded = load_uploaded()
    vids = sorted(f for f in os.listdir(OUT) if f.endswith(".mp4")) if os.path.isdir(OUT) else []
    todo = [v for v in vids if v not in uploaded][:n]
    if not todo:
        print("Ziadne nove videa na nahratie.")
        return
    tok = access_token(cid, csec, rtok)
    slots = next_slots(len(todo))
    print(f"Nahravam {len(todo)} videi na YouTube (Shorts, naplanovane 8/15/20)...")
    for i, vid in enumerate(todo):
        mp4 = os.path.join(OUT, vid)
        title, desc, tags = read_meta(mp4[:-4] + ".txt")
        pa = slots[i]
        print(f"  '{title}' -> publish {pa}")
        try:
            yid = upload(tok, mp4, title, desc, tags, pa)
            uploaded.append(vid)
            save_uploaded(uploaded)
            print(f"    OK: youtube.com/watch?v={yid}")
            try:                       # custom thumbnail (nekriticke - upload uz presiel)
                jpg = mp4[:-4] + ".jpg"
                if (os.path.exists(jpg) or pick_clean_frame(mp4, jpg)) and yid:
                    set_thumbnail(tok, yid, jpg)
            except Exception as e:
                print(f"    thumbnail zlyhal (nekriticke): {str(e)[:140]}")
        except Exception as e:
            print(f"    CHYBA: {str(e)[:300]}")
    print("HOTOVO.")


if __name__ == "__main__":
    main()
