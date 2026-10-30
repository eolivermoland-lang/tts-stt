#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if grep -q "CHANGE-ME" wrangler.toml; then
  echo "TTS_URL er fortsatt placeholder."
  echo "Start TTS-serveren og tunnel.sh, eller lim inn tunnel-URLen i wrangler.toml."
  exit 1
fi

if [[ ! -f .robot_token || ! -f "$HOME/voice-server/.secret" ]]; then
  echo "Mangler tokens. Kjor ./setup-secrets.sh foerst."
  exit 1
fi

npx wrangler deploy
