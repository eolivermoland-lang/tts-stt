# Robot Dog API

Cloudflare Worker som er API-et roboten kaller.

```
POST /stt             WAV 16 kHz mono        -> {"text":"..."}
POST /chat            {"messages":[...]}     -> {"text":"..."}
POST /say             {"text":"..."}         -> audio/wav (din stemme)
GET  /voices                                -> stemmeprofiler
POST /voices/reload                         -> last stemmer på nytt
GET  /status                                -> {"ok":true}
```

All trafikk krever:

```
Authorization: Bearer <ROBOT_TOKEN>
```

Workeren bruker Cloudflare Workers AI til STT og chat, og proxyer `/say` til
TTS-serveren paa Mac-en via `TTS_URL`.

## Oppsett

```bash
cd ~/robot-dog-api
./setup.sh
npx wrangler login
```

`setup.sh` kjorer `npm install` og fikser workerd-binærfila hvis npm har
blokkert install-scriptet. `wrangler login` aapner nettleseren og krever en
gratis Cloudflare-konto. Du maa gjore denne delen selv.

Legg inn hemmeligheter (scriptet sjekker at du er logget inn):

```bash
./setup-secrets.sh
```

Manuelt tilsvarer det:

```bash
cat ~/voice-server/.secret | npx wrangler secret put TTS_SECRET
cat .robot_token | npx wrangler secret put ROBOT_TOKEN
```

`TTS_URL` ligger i `wrangler.toml`. `~/voice-server/tunnel.sh` oppdaterer den
automatisk naar tunnelen starter. Du kan ogsaa gjore det manuelt:

```toml
[vars]
TTS_URL = "https://....trycloudflare.com"
```

Deploy:

```bash
./deploy.sh
```

## Test lokalt (uten Cloudflare-konto)

Test Workeren mot den lokale TTS-serveren med mocket AI:

```bash
ROBOT_TOKEN="$(cat .robot_token)" \
TTS_SECRET="$(cat ~/voice-server/.secret)" \
TTS_URL="http://127.0.0.1:8000" \
node test_worker.mjs
```

Dette tester `/status`, `/say`, `/stt` og `/chat`, og skriver
`worker_svar.wav`. Krever at `~/voice-server/start.sh` kjorer.

## Test etter deploy

Bytt ut `DITTNAVN` med Cloudflare-subdomenet ditt:

```bash
curl https://robot-dog-api.DITTNAVN.workers.dev/status \
  -H "Authorization: Bearer $(cat .robot_token)"

curl -X POST https://robot-dog-api.DITTNAVN.workers.dev/chat \
  -H "Authorization: Bearer $(cat .robot_token)" \
  -H "content-type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hei Bingo!"}]}'

curl -X POST https://robot-dog-api.DITTNAVN.workers.dev/stt \
  -H "Authorization: Bearer $(cat .robot_token)" \
  -H "content-type: audio/wav" \
  --data-binary @opptak.wav

curl -X POST https://robot-dog-api.DITTNAVN.workers.dev/say \
  -H "Authorization: Bearer $(cat .robot_token)" \
  -H "content-type: application/json" \
  -d '{"text":"Hei! Jeg er Bingo."}' \
  --output svar.wav

afplay svar.wav
```

## Bingo Studio

Det finnes et eget desktopprogram i `~/robot-dog-chat` som gjør hele runden:
mikrofon -> `/stt` -> `/chat` -> `/say` -> høyttaler. Der kan du også styre
personlighet, modell, stemmeprofil og taleparametere.

```bash
cd ~/robot-dog-chat
./setup.sh
./run.sh
```

Se `~/robot-dog-chat/README.md` for kommandoer og feilsøking.

## Rekkefolge

1. Spill inn `~/voice-server/min_stemme.wav`
2. Start `~/voice-server/start.sh`
3. Start `~/voice-server/tunnel.sh` (oppdaterer `TTS_URL`)
4. `npx wrangler login` (forste gang)
5. `./setup-secrets.sh`
6. `./deploy.sh`
7. Test med curl

## Personlighet og svarlengde

`/chat` godtar disse valgfrie feltene:

```json
{
  "messages": [{"role": "user", "content": "Hei!"}],
  "system": "Du er Bingo ...",
  "model": "@cf/google/gemma-4-26b-a4b-it",
  "temperature": 0.8,
  "max_completion_tokens": 80
}
```

Hvis `system` mangler, brukes standardprompten i `src/index.js`: én kort setning
på cirka 12 ord, uten emoji. Bingo Studio sender sin egen prompt fra
innstillingene. `max_completion_tokens` begrenses til 16–512.

`/say` godtar også `voice`, `exaggeration`, `cfg_weight`, `temperature`,
`repetition_penalty`, `top_p`, `lang_code` og `max_tokens`. Workeren videresender
disse til TTS-serveren.

Gemma 4 bruker OpenAIs responsformat (`choices[0].message.content`) og har
reasoning på som standard. Workeren skrur derfor av reasoning med
`chat_template_kwargs: { enable_thinking: false }`; ellers kan svaret bli tomt
når tokenbudsjettet er lite. Andre modeller bruker `max_tokens`.

Whisper krever at `audio` sendes som base64, ikke som en byte-array. Det gjør
Workeren før den kaller `@cf/openai/whisper-large-v3-turbo`.
