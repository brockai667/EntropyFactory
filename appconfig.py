#!/usr/bin/env python3
"""Spolocne nacitanie configu: config.json + prekrytie tajomstvami z ENV (pre cloud)
a oprava ffmpeg/ffprobe cesty (Windows cesta vs. Linux PATH)."""
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

# tajne hodnoty: v cloude prichadzaju cez ENV (GitHub Actions secrets),
# lokalne su v config.json
ENV_MAP = {
    "youtube_client_id": "YOUTUBE_CLIENT_ID",
    "youtube_client_secret": "YOUTUBE_CLIENT_SECRET",
    "youtube_refresh_token": "YOUTUBE_REFRESH_TOKEN",
}


def load():
    with open(os.path.join(ROOT, "config.json"), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # prekry tajomstva z prostredia, ak su nastavene
    for key, env in ENV_MAP.items():
        val = os.environ.get(env)
        if val:
            cfg[key] = val
    # ffmpeg/ffprobe: ak ulozena cesta neexistuje (napr. na Linuxe), pouzi PATH
    for key, fallback in (("ffmpeg", "ffmpeg"), ("ffprobe", "ffprobe")):
        path = cfg.get(key, fallback)
        if not path or not os.path.exists(path):
            cfg[key] = fallback
    return cfg
