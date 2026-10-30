# Bingo Studio

Et desktop-program i Python for å teste og styre robothunden Bingo:

```text
mikrofon -> /stt -> /chat -> /say -> høyttaler
```

Programmet bruker API-et:

```text
https://robot-dog-api.eolivermoland.workers.dev
```

Du kan snakke med Bingo, skrive til den, bytte personlighet, velge
stemmeprofil og justere hvordan stemmen skal høres ut.

## Start

```bash
cd ~/robot-dog-chat
./setup.sh      # bare første gang, eller etter nye avhengigheter
./run.sh
```

Du kan også dobbeltklikke på `Bingo Studio.command`.

Før du starter må TTS-serveren og tunnelen kjøre:

```bash
# Terminal 1
cd ~/voice-server
./start.sh

# Terminal 2
cd ~/voice-server
./tunnel.sh
```

Hvis tunnelen har fått ny URL, må Workeren deployes på nytt:

```bash
cd ~/robot-dog-api
./deploy.sh
```

## Fanene

### Bingo

- Navn på robothunden.
- Personlighet: nysgjerrig valp, rolig hjelper, morsom, kort og presis,
  eller egendefinert.
- Systemprompt: skriv fritt hvordan Bingo skal oppføre seg og snakke.
- Modell: Cloudflare Workers AI-modell. Standard er Gemma 4.
- Kreativitet, maks tokens og hvor mange runder Bingo husker.

### Stemme

- Velg blant stemmeprofilene som ligger i `~/voice-server/voices`
  (og `min_stemme.wav`).
- Legg til en ny WAV-fil direkte fra programmet. Den kopieres til
  stemmemappen og lastes inn på nytt uten restart.
- Hør på en testtekst før du bruker stemmen i samtalen.
- Stilpresets: Nøytral, Rolig, Glad, Oppspilt og Dramatisk.
- Finjustering:
  - **Exaggeration** – hvor mye følelser/uttrykk stemmen skal ha.
  - **CFG-vekt** – hvor tett den skal følge referansestemmen.
  - **Temperatur** – variasjon i genereringen.
  - **Repetisjon** – straff for gjentakelser.
  - **Top-p** – hvor mange sannsynlige token som vurderes.
- Språk: `no` for norsk.

Referanseopptaket betyr mest for hvordan stemmen låter. 20–30 sekunder ren
tale, én person, uten musikk og støy gir best resultat.

### Lyd

- Velg mikrofon og høyttaler.
- **Automatisk (VAD)**: starter når du snakker, og stopper etter stillhet.
- **Trykk for å snakke**: start og stopp opptaket selv.
- Støygrense, stillhetstid, maks opptakslengde og pre-roll.
- Trim stillhet før lyden sendes til STT.
- Test mikrofon i 3 sekunder.

### API

- API-URL og `ROBOT_TOKEN`.
- Test tilkobling, se API- og TTS-status.
- Oppdater eller last inn stemmeprofiler på nytt.
- Tokenet lagres i `.env` med filrettigheter kun for deg.

### Logg

- Sanntidslogg for opptak, STT, chat, TTS og feil.
- Lagre loggen til fil.

## Bruk

| Handling | Resultat |
| --- | --- |
| `Snakk` | Starter opptak. I VAD-modus stopper det automatisk. |
| `Send` / Enter | Sender skrevet tekst. |
| `Stopp lyd` | Stopper avspilling. |
| `Spill av igjen` | Spiller siste Bingo-svar. |
| `Ny samtale` | Nullstiller samtaleminne og chat. |
| `Eksporter` | Lagrer samtalen som tekstfil. |
| `Ctrl+R` | Start/stopp opptak. |
| `Esc` | Stopp opptak eller avspilling. |

## Legge til en ny stemme

1. Spill inn 20–30 sekunder med ren tale.
   Du kan bruke `~/voice-server/record_ref.sh`.
2. I Bingo Studio: **Stemme → Legg til WAV …**
3. Velg filen. Den kopieres til `~/voice-server/voices`.
4. Programmet laster inn stemmen på nytt. Velg den i listen.
5. Trykk **Spill av test** for å høre resultatet.

Du kan også legge WAV-filer manuelt i `~/voice-server/voices` og trykke
**Last inn på nytt**.

## API-kontrakt

Alle kall krever:

```text
Authorization: Bearer <ROBOT_TOKEN>
```

| Endepunkt | Metode | Beskrivelse |
| --- | --- | --- |
| `/status` | GET | Sjekker Workeren. |
| `/stt` | POST | WAV 16 kHz mono som body. Returnerer `{text}`. |
| `/chat` | POST | `{messages, system, model, temperature, max_completion_tokens}`. |
| `/say` | POST | `{text, voice, exaggeration, cfg_weight, temperature, repetition_penalty, top_p, lang_code, max_tokens}`. Returnerer WAV. |
| `/voices` | GET | Lister stemmeprofiler og standardverdier. |
| `/voices/reload` | POST | Laster stemmeprofiler på nytt i TTS-serveren. |

## Feilsøking

### 401 unauthorized

Tokenet i `.env` stemmer ikke med `ROBOT_TOKEN` i Cloudflare Workeren.

```bash
cat ~/robot-dog-api/.robot_token
```

Lim verdien inn i **API → Robot-token** og trykk **Lagre**.

### 403 error code 1010

Cloudflare avviser noen standard Python-brukere. Programmet sender en egen
User-Agent, så dette skal ikke skje. Hvis det likevel skjer, sjekk at du
bruker den nyeste versjonen av `api_client.py`.

### 502 på /say eller /voices

TTS-serveren eller tunnelen svarer ikke. Sjekk at `start.sh` og `tunnel.sh`
kjører. Hvis tunnelen er startet på nytt, oppdater `TTS_URL` i
`~/robot-dog-api/wrangler.toml` og deploy:

```bash
cd ~/robot-dog-api
./deploy.sh
```

### Mikrofonen virker ikke

Gi Terminal tilgang:

```text
Systeminnstillinger → Personvern og sikkerhet → Mikrofon
```

Velg riktig enhet under **Lyd → Mikrofon**. Unngå iPhone-mikrofon og
Bluetooth mens du feilsøker.

### Stemmen blir hakkete eller rar

- Bruk et lengre og renere referanseopptak (20–30 sekunder).
- Prøv en annen stil, eller senk Exaggeration.
- Sjekk at Mac-en er koblet til strøm og ikke sover.
- TTS-serveren bruker 8-bit Chatterbox som standard. Bytte til fp16 gir
  bedre kvalitet, men tregere svar. Se `~/voice-server/README.md`.

### Mac-en sovner

```bash
caffeinate -dimsu
```

## Sikkerhet

- `.env` inneholder `ROBOT_TOKEN` og er bare lesbar for deg.
- `settings.json` inneholder innstillinger, ikke token.
- `.gitignore` utelukker `.env`, `.venv`, `settings.json` og lydfiler.
- Alle API-kall går over HTTPS til Cloudflare. `/say` går videre til
  TTS-serveren på Mac-en via tunnelen.

## Filer

| Fil | Beskrivelse |
| --- | --- |
| `app.py` | PySide6-desktopprogrammet. |
| `api_client.py` | HTTP-klient for Workeren. |
| `audio_engine.py` | Opptak, VAD, WAV og avspilling. |
| `settings_store.py` | Innstillinger og `.env`. |
| `workers.py` | Bakgrunnsjobber for API-kall. |
| `chat.py` | Eldre terminalversjon. Start med `./run-cli.sh`. |
| `run.sh` | Starter desktopprogrammet. |
| `setup.sh` | Lager venv og installerer avhengigheter. |
