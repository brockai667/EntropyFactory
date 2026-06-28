#!/usr/bin/env python3
"""
JEDNORAZOVE: prihlasi Entropy YouTube kanal na auto-upload a vypise REFRESH TOKEN.
Pouzitie:  python youtube_auth.py
Cita youtube_client_id + youtube_client_secret z config.json (uz su predvyplnene).
Otvori prehliadac -> PRIHLAS SA UCTOM S KANALOM "Entropy" -> Allow.
Vypisany refresh token vlozim do config.json + Actions secret YOUTUBE_REFRESH_TOKEN.
"""
import json
import os
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8725
REDIRECT = f"http://localhost:{PORT}"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
_got = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _got["code"] = q.get("code", [None])[0]
        _got["error"] = q.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>Hotovo. Zavri okno a vrat sa do terminalu.</h2>".encode("utf-8"))

    def log_message(self, *a):
        pass


def main():
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    cid, csec = cfg.get("youtube_client_id"), cfg.get("youtube_client_secret")
    if not cid or not csec:
        print("CHYBA: do config.json daj youtube_client_id a youtube_client_secret")
        return
    auth = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent"})
    srv = HTTPServer(("localhost", PORT), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("\nOtvaram prehliadac. PRIHLAS SA UCTOM S KANALOM 'Entropy' a klikni Allow...")
    try:
        webbrowser.open(auth)
    except Exception:
        print("Otvor manualne:\n", auth)
    for _ in range(300):
        if _got.get("code") or _got.get("error"):
            break
        time.sleep(1)
    srv.server_close()
    if _got.get("error") or not _got.get("code"):
        print("Zamietnute/timeout:", _got.get("error"))
        return
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "client_id": cid, "client_secret": csec, "code": _got["code"],
        "grant_type": "authorization_code", "redirect_uri": REDIRECT})
    rt = r.json().get("refresh_token")
    if not rt:
        print("Nedostal som refresh_token. Odpoved:", r.json())
        return
    print("\n=== REFRESH TOKEN (posli mi ho / daj do Actions secret YOUTUBE_REFRESH_TOKEN) ===")
    print(rt)


if __name__ == "__main__":
    main()
