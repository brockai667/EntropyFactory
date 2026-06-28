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
import sys

import requests

import appconfig

ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOADED = os.path.join(ROOT, "uploaded.json")
OUT = os.path.join(ROOT, "output")
SLOT_HOURS = [8, 15, 20]
CATEGORY = "28"   # Science & Technology


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
        except Exception as e:
            print(f"    CHYBA: {str(e)[:300]}")
    print("HOTOVO.")


if __name__ == "__main__":
    main()
