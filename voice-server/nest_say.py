import os, re, time, threading, functools, http.server, subprocess, atexit
import requests, pychromecast, soundfile as sf

NEST_NAVN = "Entryway speaker"
STEMME = "min_stemme"
TTS_URL = "http://localhost:8000/say"
FIL_PORT = 8001
BASE = os.path.dirname(os.path.abspath(__file__))
LYDMAPPE = os.path.join(BASE, "nest_lyd")
LOGG = os.path.join(BASE, "nest_tunnel.log")
os.makedirs(LYDMAPPE, exist_ok=True)

with open(os.path.join(BASE, ".secret")) as f:
    API_KEY = f.read().strip()

OFFENTLIG_URL = None
_tunnel = None


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        print("Nest hentet:", self.path)


def vent_paa_dns(url, maks=90):
    host = url.replace("https://", "").split("/")[0]
    print("Venter til Google DNS kjenner adressen...")
    start = time.time()
    while time.time() - start < maks:
        try:
            r = subprocess.run(
                ["dig", "@8.8.8.8", "+short", host],
                capture_output=True, text=True, timeout=10,
            )
            if r.stdout.strip():
                print("DNS klar.")
                time.sleep(3)
                return
        except Exception:
            pass
        time.sleep(3)
    print("DNS ikke bekreftet, prøver likevel.")


def start_filserver():
    global OFFENTLIG_URL, _tunnel
    if OFFENTLIG_URL:
        return

    handler = functools.partial(Handler, directory=LYDMAPPE)
    server = http.server.ThreadingHTTPServer(("0.0.0.0", FIL_PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("Starter tunnel for lydfiler...")
    logg = open(LOGG, "w")
    _tunnel = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{FIL_PORT}",
         "--protocol", "http2", "--no-autoupdate"],
        stdout=logg, stderr=logg,
    )
    atexit.register(lambda: _tunnel.terminate())

    for _ in range(60):
        with open(LOGG) as f:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", f.read())
        if m:
            OFFENTLIG_URL = m.group(0)
            break
        time.sleep(1)
    if not OFFENTLIG_URL:
        raise SystemExit("Fikk ikke tunnel. Se nest_tunnel.log")

    for _ in range(40):
        try:
            if requests.get(OFFENTLIG_URL + "/", timeout=5).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    print("Tunnel klar:", OFFENTLIG_URL)
    vent_paa_dns(OFFENTLIG_URL)


def del_opp(tekst, maks=380):
    setninger = re.split(r"(?<=[.!?])\s+", tekst.strip())
    deler, nu = [], ""
    for s in setninger:
        if len(nu) + len(s) + 1 <= maks:
            nu = (nu + " " + s).strip()
        else:
            if nu:
                deler.append(nu)
            nu = s[:maks]
    if nu:
        deler.append(nu)
    return deler


def lag_lyd(tekst):
    r = requests.post(
        TTS_URL,
        headers={"x-api-key": API_KEY},
        json={"text": tekst, "voice": STEMME},
        timeout=180,
    )
    r.raise_for_status()
    navn = f"svar_{int(time.time() * 1000)}"
    raa = os.path.join(LYDMAPPE, navn + "_raa.wav")
    with open(raa, "wb") as f:
        f.write(r.content)

    data, sr = sf.read(raa)
    sf.write(os.path.join(LYDMAPPE, navn + ".mp3"), data, sr, format="MP3")
    os.remove(raa)
    return navn + ".mp3"


def rydd_gamle(behold=10):
    filer = sorted(f for f in os.listdir(LYDMAPPE) if f.endswith(".mp3"))
    for f in filer[:-behold]:
        try:
            os.remove(os.path.join(LYDMAPPE, f))
        except OSError:
            pass


def si(tekst):
    start_filserver()
    print("Leter etter høyttaleren...")
    casts, browser = pychromecast.get_listed_chromecasts(friendly_names=[NEST_NAVN])
    if not casts:
        print("Fant ikke Nest Mini. Sjekk navn og Wi-Fi.")
        browser.stop_discovery()
        return
    print("Fant den! Kobler til...")
    cast = casts[0]
    cast.wait()

    for del_tekst in del_opp(tekst):
        print("Lager lyd:", del_tekst)
        filnavn = lag_lyd(del_tekst)
        url = f"{OFFENTLIG_URL}/{filnavn}"

        cast.quit_app()
        time.sleep(1.5)
        cast.set_volume(0.7)
        mc = cast.media_controller

        print("Spiller av:", url)
        mc.play_media(url, "audio/mpeg")
        try:
            mc.block_until_active(timeout=15)
        except Exception as e:
            print("Nest Mini startet ikke avspilling:", e)
            break

        start = time.time()
        har_spilt = False
        sist = None
        while time.time() - start < 60:
            tilstand = mc.status.player_state
            if tilstand != sist:
                print("Status:", tilstand, "| Årsak:", mc.status.idle_reason)
                sist = tilstand
            if tilstand == "PLAYING":
                har_spilt = True
            if har_spilt and tilstand not in ("PLAYING", "BUFFERING"):
                break
            if not har_spilt and tilstand == "IDLE" and mc.status.idle_reason:
                print("Nest Mini ga opp:", mc.status.idle_reason)
                break
            time.sleep(0.3)
        print("Ferdig.")

    rydd_gamle()
    browser.stop_discovery()


if __name__ == "__main__":
    si("Hei, jeg er JoBot. Nå snakker jeg fra Nest Mini.")