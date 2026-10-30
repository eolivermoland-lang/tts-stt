# tts-stt

Robothunden Bingo: norsk tale-til-tekst, chat og tekst-til-tale med egen stemme.

Prosjektet består av tre deler:

| Mappe | Hva det er | Kjører på |
| --- | --- | --- |
| `robot-dog-chat` | Bingo Studio, desktop-klient i Python (mikrofon -> STT -> chat -> TTS -> høyttaler) | Mac / Raspberry Pi |
| `robot-dog-api` | Cloudflare Worker som er API-et roboten kaller (`/stt`, `/chat`, `/say`, `/voices`, `/status`) | Cloudflare |
| `voice-server` | Lokal TTS-server med stemmekloning (Chatterbox MLX) | Mac med Apple Silicon |

## Flyten

```text
mikrofon -> /stt -> /chat -> /say -> høyttaler
```

Workeren bruker Cloudflare Workers AI til STT og chat, og proxyer `/say` til
TTS-serveren via en Cloudflare-tunnel (`TTS_URL` i `robot-dog-api/wrangler.toml`).

## Kom i gang på Raspberry Pi

Pi-en trenger bare klienten. TTS-serveren krever Apple Silicon (MLX), så den
kjører på Mac-en.

```bash
git clone https://github.com/eolivermoland-lang/tts-stt.git
cd tts-stt/robot-dog-chat
./setup.sh
cp .env.example .env    # fyll inn ROBOT_TOKEN
./run.sh
```

`API_URL` peker på den ferdig deployede Workeren. `ROBOT_TOKEN` må være samme
verdi som hemmeligheten i Workeren.

## Kom i gang på Mac (TTS-server)

```bash
cd voice-server
python3 -m venv .venv
.venv/bin/pip install -U mlx-audio fastapi uvicorn
./start.sh          # terminal 1
./tunnel.sh         # terminal 2
```

Se `voice-server/README.md` for opptak av referansestemme og modellvalg, og
`robot-dog-api/README.md` for deploy av Workeren.

## Hemmeligheter

Disse filene er bevisst ikke i repoet:

- `.env`, `.env.*` (unntatt `.env.example`)
- `.robot_token`, `.secret`, `.dev.vars`, `.tunnel-url`
- `settings.json`, `nest_settings.json`
- modeller, lydfiler og logger

Lag dem lokalt med scriptene i hver mappe (`setup-secrets.sh`,
`record_ref.sh`, `setup.sh`).

---

## Midlertidige hemmeligheter

Dette repoet er offentlig bare for aa faa filene over paa Raspberry Pi.
Slett repoet eller gjor det privat etterpaa, og bytt `ROBOT_TOKEN` og `TTS_SECRET`.

```dotenv
API_URL=https://robot-dog-api.eolivermoland.workers.dev
ROBOT_TOKEN=0f84ebdfeb34b7d29e5641756269b9efad045bd72c17fb5af51cf61e72f5d40f
TTS_URL=https://delivering-modes-valid-broken.trycloudflare.com
TTS_SECRET=ab9289c78319a194e5032df98d3d53e74f4026746e9d1870886e0f45a9b70038
```

Pa Pi-en kan du lage `robot-dog-chat/.env` med disse verdiene, eller kopiere
fila direkte fra Mac-en.
