# Robot Dog TTS (Chatterbox MLX)

Lokal norsk TTS med din egen stemme, kjort paa Apple Silicon via MLX.

Serveren bruker en 8-bit kvantisert versjon av
`mlx-community/chatterbox-multilingual-v3` som standard. Den ligger i
`models/chatterbox-v3-8bit` og gir omtrent 3-5 sekunder per korte setning paa
denne Mac-en. Uten kvantisering var samme setning 8-12 sekunder.

## 1. Spill inn referansestemme

Ta opp 20-30 sekunder i et stille rom, med vanlig talestemme. Ikke hvisk, og
ikke ha musikk eller stoy i bakgrunnen.

Enkleste vei:

```bash
./record_ref.sh
```

Scriptet viser en tekst på ca. 60 ord som dekker norske lyder, teller ned og tar
opp 40 sekunder fra MacBook-mikrofonen. Opptaket gjøres i mikrofonens native
48 kHz og konverteres til 24 kHz mono etterpå, som er mer stabilt. Du kan slutte
å snakke når du er ferdig; stillheten på slutten klippes bort. Opptaket lagres
som `min_stemme.wav`.

Første gang må Terminal få tilgang til mikrofonen (Systeminnstillinger ->
Personvern og sikkerhet -> Mikrofon).

Hvis opptaket høres hakkete ut: lukk apper som bruker mikrofonen, og hør
avspillingen på MacBook-høyttalerne i stedet for AirPods/Bluetooth. Scriptet
kan også spille av råopptaket (48 kHz) hvis du ikke godkjenner opptaket, slik
at du kan sjekke om problemet ligger i mikrofonen eller i etterbehandlingen.

Har du allerede et opptak (`opptak.m4a`):

```bash
ffmpeg -i opptak.m4a -ar 24000 -ac 1 min_stemme.wav
```

Sjekk at den er mono og 24 kHz:

```bash
afinfo min_stemme.wav | grep -E "duration|sample rate|channels"
```

## 2. Test kloningen forst

```bash
source .venv/bin/activate
python test_tts.py
afplay test_output.wav
```

`test_tts.py` bruker `min_stemme.wav` som standard. Vil du teste med den
midlertidige testsstemmen for du har spilt inn din egen:

```bash
REF_AUDIO=test_stemme.wav python test_tts.py
afplay test_output.wav
```

## 3. Start API-serveren

```bash
./start.sh
```

Forste gang laster modellen i noen sekunder. Deretter:

```bash
curl -X POST http://localhost:8000/say \
  -H "x-api-key: $(cat .secret)" \
  -H "content-type: application/json" \
  -d '{"text":"Hei, jeg er Bingo!"}' \
  --output svar.wav

afplay svar.wav
```

Like tekster caches, saa en gjentatt hilsen svarer nesten umiddelbart.
`/health` viser modell, referansefil og cache-statistikk.

## 4. Eksponer med Cloudflare Tunnel

`cloudflared` er allerede installert. Start serveren i ett terminalvindu, og
deretter:

```bash
./tunnel.sh
```

Scriptet starter en quick tunnel, skriver URL-en til `.tunnel-url` og oppdaterer
`TTS_URL` i `~/robot-dog-api/wrangler.toml` automatisk. La terminalvinduet staa
aapent. Ctrl-C stopper tunnelen.

Quick tunnel-URL-en er ny hver gang. Hvis du vil ha fast URL, ma du lage en
navngitt tunnel med en egen Cloudflare-domenenavn.

## 5. Deploy Workeren

```bash
cd ~/robot-dog-api
npx wrangler login       # forste gang, aapner nettleser
./setup-secrets.sh
./deploy.sh
```

Se `~/robot-dog-api/README.md` for test av hele kjeden.

## 6. Hold Mac-en vaaken

```bash
caffeinate -dimsu
```

Ha Mac-en tilkoblet strom. Lokk eller dvale stopper TTS-serveren.

## Flere stemmer

Legg flere WAV-filer i `voices/`. Filnavnet blir navnet på stemmen:

```bash
cp annen_stemme.wav voices/rolig.wav
```

Deretter kan du trykke **Last inn på nytt** i Bingo Studio, eller kalle:

```bash
curl -X POST http://localhost:8000/voices/reload \
  -H "x-api-key: $(cat .secret)"
```

Serveren regner ut conditioning på nytt uten restart. Standardstemmen er
fortsatt `min_stemme.wav`.

## Endepunkter

- `GET /health` (ingen auth) – sjekk at server, modell og stemmer er klare.
- `GET /voices` med `x-api-key` – lister stemmeprofiler og standardverdier.
- `POST /voices/reload` med `x-api-key` – laster stemmeprofiler på nytt.
- `POST /say` med `x-api-key` og for eksempel:

```json
{
  "text": "Hei, jeg er Bingo!",
  "voice": "min_stemme",
  "exaggeration": 0.7,
  "cfg_weight": 0.4,
  "temperature": 0.9,
  "repetition_penalty": 1.2,
  "top_p": 1.0,
  "lang_code": "no",
  "max_tokens": 1000
}
```

Returnerer `audio/wav`. Uten `voice` brukes `min_stemme`. `exaggeration`,
`cfg_weight`, `temperature`, `repetition_penalty` og `top_p` kan justeres per
forespørsel. `speed` støttes ikke av Chatterbox og ignoreres.

## Filer

- `.secret` - delt hemmelighet mellom Worker og TTS-server
- `.venv/` - Python-miljo
- `min_stemme.wav` - referansestemmen din (ma lages)
- `voices/` - ekstra stemmeprofiler (valgfritt)
- `test_stemme.wav` - midlertidig testsstemme fra macOS, ikke din stemme
- `models/chatterbox-v3-8bit/` - standardmodellen (rask, 887 MB)
- `models/chatterbox-v3-fp16/` - alternativ med hoyere kvalitet (1,3 GB)
- `models/chatterbox-v3-4bit/` - eksperimentell, ikke standard
- `start.sh` - starter TTS-serveren
- `tunnel.sh` - starter Cloudflare Tunnel og oppdaterer Workeren
- `record_ref.sh` - tar opp referansestemmen med MacBook-mikrofonen
- `test_tts.py` - tester kloning uten API

## Bytt modell

```bash
# hoyere kvalitet, tregere
MODEL_ID="$PWD/models/chatterbox-v3-fp16" ./start.sh

# original F32-modell fra Hugging Face
MODEL_ID="mlx-community/chatterbox-multilingual-v3" ./start.sh
```

## Lytt til teststemmene

Disse er laget med den midlertidige teststemmen (`test_stemme.wav`), ikke din
stemme. De viser kvalitetsforskjellen mellom modellene:

```bash
afplay samples/8bit.wav       # standard, rask
afplay samples/fp16.wav       # hoyere kvalitet, tregere
afplay samples/4bit.wav       # eksperimentell, lavere kvalitet
afplay samples/f32-test.wav   # original F32
afplay samples/8bit-short.wav # kort hilsen
```

8-bit og 4-bit var omtrent like raske her, saa 8-bit er standard fordi
kvaliteten er bedre.

## Feilsoking

- `referanselyd mangler`: spill inn `min_stemme.wav` forst.
- `TTS-serveren svarer ikke`: sjekk at `./start.sh` kjorer i et annet vindu.
- `502` fra Workeren: tunnel-URL-en er utdatert, eller TTS-serveren er nede.
- Langsomt svar: bruk 8-bit-modellen, hold svarene korte, og sjekk at Mac-en
  ikke er i dvale eller under tung last.
