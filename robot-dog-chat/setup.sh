#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "Oppretter virtuelt miljø ..."
if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi

echo "Installerer avhengigheter ..."
.venv/bin/python -m pip install --upgrade pip >/dev/null
.venv/bin/python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  TOKEN=""
  for candidate in "$HOME/robot-dog-api/.robot_token" ".robot_token"; do
    if [[ -f "$candidate" ]]; then
      TOKEN="$(tr -d '\r\n' < "$candidate")"
      break
    fi
  done

  umask 077
  {
    echo "API_URL=https://robot-dog-api.eolivermoland.workers.dev"
    if [[ -n "$TOKEN" ]]; then
      echo "ROBOT_TOKEN=$TOKEN"
    else
      echo "ROBOT_TOKEN=CHANGE_ME"
    fi
  } > .env
  chmod 600 .env
  echo "Skrev .env"
fi

if grep -q '^ROBOT_TOKEN=CHANGE_ME' .env; then
  echo
  echo "ROBOT_TOKEN mangler i .env."
  echo "Legg inn tokenet fra ~/robot-dog-api/.robot_token, eller kjør:"
  echo "  cat ~/robot-dog-api/.robot_token"
  echo "og lim det inn i .env."
  exit 1
fi

chmod 600 .env 2>/dev/null || true

echo
echo "Ferdig. Start samtalen med:"
echo "  ./run.sh"
