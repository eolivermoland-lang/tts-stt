#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
  echo "TTS-serveren svarer ikke paa http://localhost:8000"
  echo "Start den foerst: ./start.sh"
  exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared mangler. Kjor: brew install cloudflared"
  exit 1
fi

LOG="tunnel.log"
: > "$LOG"

echo "Starter Cloudflare Tunnel (HTTP/2) ..."
# HTTP/2 er mer robust enn QUIC paa nett som blokkerer UDP.
cloudflared tunnel --url http://localhost:8000 --protocol http2 --no-autoupdate > "$LOG" 2>&1 &
TUNNEL_PID=$!

cleanup() {
  kill "$TUNNEL_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

URL=""
for _ in $(seq 1 60); do
  URL=$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)
  if [[ -n "$URL" ]]; then
    break
  fi
  if ! kill -0 "$TUNNEL_PID" 2>/dev/null; then
    echo "cloudflared stoppet. Se $LOG"
    exit 1
  fi
  sleep 1
done

if [[ -z "$URL" ]]; then
  echo "Fant ingen tunnel-URL. Se $LOG"
  exit 1
fi

printf '%s\n' "$URL" > .tunnel-url
echo "Tunnel klar: $URL"
echo "Oppdaterer TTS_URL i ~/robot-dog-api/wrangler.toml ..."
sed -i '' "s|^TTS_URL = .*|TTS_URL = \"$URL\"|" "$HOME/robot-dog-api/wrangler.toml"
echo "OK. Deploy Workeren med: cd ~/robot-dog-api && npx wrangler deploy"
echo "La denne terminalen staa aapen. Ctrl-C stopper tunnelen."

wait "$TUNNEL_PID"
