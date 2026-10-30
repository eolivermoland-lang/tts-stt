#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .venv/bin/activate ]]; then
  echo "Mangler .venv. Kjor: python3.15 -m venv .venv && .venv/bin/pip install -U mlx-audio fastapi uvicorn"
  exit 1
fi

source .venv/bin/activate

if [[ ! -f .secret ]]; then
  openssl rand -hex 32 > .secret
  echo "Lagde ny .secret"
fi

export TTS_SECRET="$(cat .secret)"
export REF_AUDIO="${REF_AUDIO:-min_stemme.wav}"

if [[ -z "${MODEL_ID:-}" ]]; then
  if [[ -d models/chatterbox-v3-8bit ]]; then
    export MODEL_ID="$PWD/models/chatterbox-v3-8bit"
  else
    export MODEL_ID="mlx-community/chatterbox-multilingual-v3"
  fi
fi

export PORT="${PORT:-8000}"

echo "TTS-server: http://0.0.0.0:${PORT}"
echo "Referanse:  ${REF_AUDIO}"
echo "Modell:     ${MODEL_ID}"
echo "Secret:     .secret (bruk samme verdi i Cloudflare Workeren)"

exec uvicorn tts_server:app --host 0.0.0.0 --port "${PORT}"
