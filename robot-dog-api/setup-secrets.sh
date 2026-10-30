#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .robot_token ]]; then
  printf '%s' "$(openssl rand -hex 32)" > .robot_token
  chmod 600 .robot_token
  echo "Lagde .robot_token"
fi

if [[ ! -f "$HOME/voice-server/.secret" ]]; then
  echo "Mangler ~/voice-server/.secret. Start TTS-serveren en gang foerst."
  exit 1
fi

WHOAMI="$(npx wrangler whoami 2>&1 || true)"
if grep -qi "not authenticated" <<< "$WHOAMI"; then
  echo "Du er ikke logget inn. Kjor: npx wrangler login"
  exit 1
fi

echo "Setter ROBOT_TOKEN ..."
npx wrangler secret put ROBOT_TOKEN < .robot_token

echo "Setter TTS_SECRET ..."
npx wrangler secret put TTS_SECRET < "$HOME/voice-server/.secret"

echo "Hemmeligheter satt."
