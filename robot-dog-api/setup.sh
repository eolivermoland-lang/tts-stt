#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Installerer npm-pakker ..."
npm install

# npm kan blokkere install-scriptet til workerd. Da mangler den native
# binærfila, og wrangler feiler med en platform-feil. Fiks det her.
if [[ ! -x node_modules/workerd/bin/workerd ]]; then
  echo "Installerer workerd-binærfila ..."
  node node_modules/workerd/install.js
fi

npx wrangler --version
echo "Klar. Neste: npx wrangler login"
