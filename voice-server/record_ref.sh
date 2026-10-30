#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

DURATION="${DURATION:-40}"
AUDIO_DEVICE="${AUDIO_DEVICE:-1}"
PREROLL=4
RECORD_SECONDS=$((DURATION + PREROLL + 2))
OUT="min_stemme.wav"
RAW=".min_stemme_raw.wav"
CANDIDATE=".min_stemme_candidate.wav"
LOG="$(mktemp -t record_ref)"
FFMPEG_PID=""

cleanup() {
  if [[ -n "${FFMPEG_PID:-}" ]]; then
    kill "$FFMPEG_PID" 2>/dev/null || true
  fi
  rm -f "$RAW" "$CANDIDATE" "$CANDIDATE.trim.wav" "$LOG"
}
trap cleanup EXIT

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg mangler. Installer det først."
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "Mangler .venv. Kjør oppsettet i README.md først."
  exit 1
fi

TEXT="Hei! Jeg heter Oliver, og dette er stemmen min.
Jeg bor i Norge, og jeg har på meg en blå skjorte.
Jeg liker å gå tur, høre på musikk og kjøre snowboard når det er snø.
Hva synes du om været i dag? Det er ganske fint, synes jeg.
Nå skal robothunden Bingo få snakke med stemmen min. Det blir gøy!"

while true; do
  clear 2>/dev/null || true
  cat <<EOF
============================================================
  Spill inn referansestemmen din (20-30 sekunder)
============================================================

Slik får du best resultat:

  * Sitt i et stille rom. Skru av vifte, musikk og TV.
  * Lukk andre apper som bruker mikrofonen (Voice Memos, Zoom, Discord).
  * Bruk MacBook-mikrofonen. Unngå AirPods/Bluetooth.
  * Hør avspillingen på MacBook-høyttalerne, ikke AirPods/Bluetooth.
  * Ha munnen ca. 15-20 cm fra mikrofonen, litt på skrå.
  * Snakk med vanlig stemme. Ikke hvisk, og ikke prøv å være skuespiller.
  * Les rolig og naturlig. Ikke stress.
  * Ta opp hele teksten i ett sammenhengende opptak.
  * Hvis du gjør en feil, eller det høres hakkete ut: ta opp på nytt.

Les denne teksten:

------------------------------------------------------------
$TEXT
------------------------------------------------------------

Etter nedtellingen har du ca. ${DURATION} sekunder på deg. Du kan slutte å
snakke når du er ferdig; stillheten på slutten klippes bort.

Trykk Enter for å starte.
EOF
  read -r _

  echo
  echo "Starter mikrofonen ..."
  # Ta opp i mikrofonenes native 48 kHz. Det er mer stabilt enn å resample
  # direkte fra AVFoundation, og vi konverterer til 24 kHz etterpå.
  ffmpeg -y -f avfoundation -thread_queue_size 2048 -i ":${AUDIO_DEVICE}" \
    -t "$RECORD_SECONDS" -ar 48000 -ac 1 "$RAW" >"$LOG" 2>&1 &
  FFMPEG_PID=$!
  sleep 1

  echo "3..."
  sleep 1
  echo "2..."
  sleep 1
  echo "1..."
  sleep 1
  echo "Snakk nå! (opptaket stopper automatisk)"

  if ! wait "$FFMPEG_PID"; then
    FFMPEG_PID=""
    echo
    echo "Opptaket feilet. Vanlige årsaker:"
    echo "  * Terminal har ikke tilgang til mikrofonen."
    echo "  * Feil lydenhet. Prøv: AUDIO_DEVICE=1 ./record_ref.sh"
    echo
    echo "Siste feilmelding:"
    tail -20 "$LOG"
    exit 1
  fi
  FFMPEG_PID=""

  # Klipp bort stillhet i starten og slutten, og konverter til 24 kHz mono.
  ffmpeg -y -i "$RAW" \
    -af "aresample=async=1:first_pts=0,silenceremove=start_periods=1:start_duration=0.2:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_duration=0.2:start_threshold=-45dB,areverse" \
    -ar 24000 -ac 1 "$CANDIDATE.trim.wav" >/dev/null 2>&1
  mv -f "$CANDIDATE.trim.wav" "$CANDIDATE"

  DUR="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$CANDIDATE")"
  VOL="$(ffmpeg -hide_banner -i "$CANDIDATE" -af volumedetect -f null - 2>&1 || true)"
  MEAN="$(printf '%s\n' "$VOL" | awk -F': ' '/mean_volume/ {print $2; exit}')"
  MAX="$(printf '%s\n' "$VOL" | awk -F': ' '/max_volume/ {print $2; exit}')"

  echo
  echo "Opptak: ${DUR} sekunder"
  echo "Snittnivå: ${MEAN:-ukjent}"
  echo "Toppnivå:  ${MAX:-ukjent}"

  # Finn digitale hull (eksakte nuller) som kan gi hakkete avspilling.
  GAPS="$(.venv/bin/python - "$CANDIDATE" <<'PY' || true
import sys, wave
import numpy as np

with wave.open(sys.argv[1], "rb") as w:
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    sr = w.getframerate()

z = (x == 0).astype(np.int8)
d = np.diff(np.concatenate(([0], z, [0])))
starts = np.where(d == 1)[0]
ends = np.where(d == -1)[0]
duration = len(x) / sr
runs = []
for start, end in zip(starts, ends):
    start_s, end_s = start / sr, end / sr
    # Ignorer stillhet helt i starten/slutten; den er allerede trimmet.
    if start_s < 0.25 or end_s > duration - 0.25:
        continue
    run_ms = (end - start) / sr * 1000.0
    if run_ms >= 10.0:
        runs.append(run_ms)
print(f"{len(runs)} {sum(runs):.0f} {max(runs) if runs else 0:.0f}")
PY
)"
  read -r GAP_COUNT GAP_TOTAL_MS GAP_MAX_MS <<<"${GAPS:-0 0 0}"

  if [[ "${GAP_COUNT:-0}" -gt 0 ]]; then
    echo "Digitale hull: ${GAP_COUNT} (${GAP_TOTAL_MS} ms, lengste ${GAP_MAX_MS} ms)"
    if [[ "${GAP_TOTAL_MS:-0}" -gt 20 ]]; then
      echo
      echo "Advarsel: opptaket har korte avbrudd. Det kan gi hakkete stemme."
      echo "Lukk apper som bruker mikrofonen, og ta opp på nytt."
    fi
  fi
  echo

  if awk -v d="$DUR" 'BEGIN {exit !(d < 15)}'; then
    echo "Opptaket er kortere enn 15 sekunder. Prøv en gang til."
    echo
    read -r -p "Trykk Enter for å prøve igjen." _
    continue
  fi

  if awk -v m="${MAX% dB}" 'BEGIN {exit !(m > -1.0)}'; then
    echo "Advarsel: lyden er nesten for høy og kan klippe. Flytt deg litt lenger"
    echo "fra mikrofonen hvis du hører forvrengning."
  fi

  if awk -v m="${MEAN% dB}" 'BEGIN {exit !(m < -35)}'; then
    echo "Advarsel: opptaket er ganske svakt. Prøv å snakke litt høyere eller"
    echo "sitte nærmere mikrofonen."
  fi

  echo "Slik høres det ut:"
  afplay "$CANDIDATE" || true
  echo

  ACCEPTED=""
  while [[ -z "$ACCEPTED" ]]; do
    read -r -p "Bruke dette opptaket? [j/n] " ANSWER
    case "$ANSWER" in
      j|J|ja|Ja|JA)
        ACCEPTED=1
        ;;
      n|N|nei|Nei|NEI)
        ACCEPTED=0
        ;;
      *)
        echo "Svar j for ja eller n for nei."
        ;;
    esac
  done

  if [[ "$ACCEPTED" == "0" ]]; then
    echo
    read -r -p "Vil du høre råopptaket for å sjekke om feilen er i mikrofonen? [j/N] " HEAR_RAW
    case "$HEAR_RAW" in
      j|J|ja|Ja|JA)
        echo "Råopptak (48 kHz):"
        afplay "$RAW" || true
        echo
        echo "Hvis råopptaket også er hakkete, er problemet mikrofonen eller"
        echo "systemet. Prøv å lukke andre apper, eller bruk iPhone-mikrofonen:"
        echo "  AUDIO_DEVICE=0 ./record_ref.sh"
        ;;
    esac
    echo
    echo "OK, prøver igjen."
    continue
  fi

  break
done

if [[ -f "$OUT" ]]; then
  mv -f "$OUT" "${OUT%.wav}.prev.wav"
  echo "Forrige opptak er lagret som ${OUT%.wav}.prev.wav"
fi

mv -f "$CANDIDATE" "$OUT"
echo
echo "Lagret: $OUT"
afinfo "$OUT" | grep -E "duration|sample rate|channels" || true

echo
read -r -p "Vil du teste klonen med en gang? [j/N] " TEST_NOW
case "$TEST_NOW" in
  j|J|ja|Ja|JA)
    echo
    .venv/bin/python test_tts.py
    echo
    echo "Spiller av test_output.wav ..."
    afplay test_output.wav || true
    ;;
esac

cat <<EOF

Ferdig. Neste steg:

  ./start.sh              # start TTS-serveren
  ./tunnel.sh             # i et annet terminalvindu

Deretter Cloudflare:
  cd ~/robot-dog-api
  ./setup.sh
  npx wrangler login
  ./setup-secrets.sh
  ./deploy.sh
EOF
