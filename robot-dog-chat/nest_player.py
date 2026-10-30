"""Spiller lyd fra Bingo Studio på Google Nest Mini (Cast + cloudflared)."""
from __future__ import annotations

import atexit
import functools
import http.server
import io
import json
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pychromecast
import requests
import soundfile as sf
from PySide6.QtCore import QThread, Signal

BASE = Path(__file__).resolve().parent
LYDMAPPE = BASE / "nest_lyd"
LOGG = BASE / "nest_tunnel.log"
INNSTILLINGER = BASE / "nest_settings.json"
FIL_PORT = 8001
VOLUM = 0.7

LYDMAPPE.mkdir(exist_ok=True)


def les_innstillinger() -> dict:
    try:
        return json.loads(INNSTILLINGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


_navn = les_innstillinger().get("navn") or "Entryway speaker"
_lock = threading.Lock()
_offentlig_url = None
_tunnel = None
_server_startet = False
_cast = None
_browser = None


def hent_navn() -> str:
    return _navn


def lagre_innstillinger(paa: bool, navn: str) -> None:
    global _navn
    navn = navn.strip() or "Entryway speaker"
    if navn != _navn:
        _navn = navn
        _nullstill_cast()
    try:
        INNSTILLINGER.write_text(
            json.dumps({"paa": bool(paa), "navn": navn}), encoding="utf-8"
        )
    except Exception:
        pass


class _Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, *args):
        pass


def _cloudflared() -> str:
    funnet = shutil.which("cloudflared")
    if funnet:
        return funnet
    for sti in ("/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"):
        if Path(sti).exists():
            return sti
    raise RuntimeError("cloudflared mangler. Kjør: brew install cloudflared")


def _vent_paa_dns(url: str, maks: int = 90) -> None:
    host = url.replace("https://", "").split("/")[0]
    start = time.time()
    while time.time() - start < maks:
        try:
            r = subprocess.run(
                ["dig", "@8.8.8.8", "+short", host],
                capture_output=True, text=True, timeout=10,
            )
            if r.stdout.strip():
                time.sleep(3)
                return
        except Exception:
            pass
        time.sleep(3)


def _start_tunnel() -> None:
    global _offentlig_url, _tunnel, _server_startet
    if _offentlig_url and _tunnel and _tunnel.poll() is None:
        return
    _offentlig_url = None

    if not _server_startet:
        handler = functools.partial(_Handler, directory=str(LYDMAPPE))
        server = http.server.ThreadingHTTPServer(("0.0.0.0", FIL_PORT), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _server_startet = True

    logg = open(LOGG, "w")
    _tunnel = subprocess.Popen(
        [_cloudflared(), "tunnel", "--url", f"http://localhost:{FIL_PORT}",
         "--protocol", "http2", "--no-autoupdate"],
        stdout=logg, stderr=logg,
    )
    atexit.register(lambda: _tunnel and _tunnel.terminate())

    url = None
    for _ in range(60):
        try:
            m = re.search(
                r"https://[a-z0-9-]+\.trycloudflare\.com",
                LOGG.read_text(errors="ignore"),
            )
        except Exception:
            m = None
        if m:
            url = m.group(0)
            break
        time.sleep(1)
    if not url:
        raise RuntimeError("Fikk ikke tunnel for Nest Mini. Se nest_tunnel.log")

    for _ in range(40):
        try:
            if requests.get(url + "/", timeout=5).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    _vent_paa_dns(url)
    _offentlig_url = url


def _nullstill_cast() -> None:
    global _cast, _browser
    try:
        if _browser:
            _browser.stop_discovery()
    except Exception:
        pass
    _cast = None
    _browser = None


def _finn_cast():
    global _cast, _browser
    if _cast is not None:
        return _cast
    casts, browser = pychromecast.get_listed_chromecasts(friendly_names=[_navn])
    if not casts:
        browser.stop_discovery()
        raise RuntimeError(
            f"Fant ikke «{_navn}». Sjekk navnet og at Mac og Nest Mini er på samme Wi-Fi."
        )
    _cast = casts[0]
    _browser = browser
    _cast.wait()
    return _cast


def _spill_url(cast, url: str, avbryt: threading.Event) -> None:
    if avbryt.is_set():
        return
    cast.quit_app()
    time.sleep(1.5)
    cast.set_volume(VOLUM)
    mc = cast.media_controller
    mc.play_media(url, "audio/mpeg")
    mc.block_until_active(timeout=15)

    start = time.time()
    har_spilt = False
    while True:
        if avbryt.is_set():
            cast.quit_app()
            return
        tilstand = mc.status.player_state
        if tilstand == "PLAYING":
            har_spilt = True
        if har_spilt and tilstand not in ("PLAYING", "BUFFERING"):
            return
        if not har_spilt and time.time() - start > 30:
            raise RuntimeError("Nest Mini begynte ikke å spille av lyden.")
        if time.time() - start > 180:
            return
        time.sleep(0.3)


def _rydd(behold: int = 10) -> None:
    filer = sorted(p for p in LYDMAPPE.glob("*.mp3"))
    for p in filer[:-behold]:
        try:
            p.unlink()
        except OSError:
            pass


def spill(wav: bytes, avbryt: threading.Event) -> None:
    with _lock:
        _start_tunnel()
        navn = f"svar_{int(time.time() * 1000)}.mp3"
        data, sr = sf.read(io.BytesIO(wav))
        sf.write(str(LYDMAPPE / navn), data, sr, format="MP3")
        url = f"{_offentlig_url}/{navn}"
        try:
            _spill_url(_finn_cast(), url, avbryt)
        except Exception:
            if avbryt.is_set():
                return
            _nullstill_cast()
            _spill_url(_finn_cast(), url, avbryt)
        _rydd()


def forbered_i_bakgrunnen() -> None:
    def jobb():
        try:
            with _lock:
                _start_tunnel()
                _finn_cast()
        except Exception:
            pass

    threading.Thread(target=jobb, daemon=True).start()


class NestPlaybackThread(QThread):
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, data: bytes, parent=None):
        super().__init__(parent)
        self.data = data
        self._avbryt = threading.Event()

    def run(self) -> None:
        try:
            spill(self.data, self._avbryt)
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def stop(self) -> None:
        self._avbryt.set()
