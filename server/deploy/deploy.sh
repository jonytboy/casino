#!/usr/bin/env bash
# Build the page, ship the server, restart it. Run from a checkout on your
# machine, with SSH access to the box.
#
#   ./deploy.sh root@casinocarib.com
#
# Idempotent: safe to run repeatedly, and it never touches ./data on the server.
set -euo pipefail

HOST="${1:?usage: deploy.sh user@host [remote-dir]}"
DIR="${2:-/opt/casino}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

echo "==> building the page"
python3 "$REPO/build_web.py" serve

echo "==> syncing to $HOST:$DIR"
ssh "$HOST" "mkdir -p $DIR"
# --delete keeps the remote copy honest, and excluding data/ means a deploy can
# never remove the balances. That exclusion is the only thing standing between
# a routine deploy and wiping every player's coins, so leave it alone.
rsync -az --delete \
  --exclude data/ --exclude .env --exclude node_modules/ --exclude test/ \
  "$REPO/server/" "$HOST:$DIR/server/"
rsync -az "$HERE/docker-compose.yml" "$HERE/Caddyfile" "$HOST:$DIR/"

echo "==> starting"
ssh "$HOST" "cd $DIR && test -f .env || { echo 'no .env on the server — copy deploy/.env.example to $DIR/.env and fill it in'; exit 1; }"
ssh "$HOST" "cd $DIR && docker compose up -d --build"

echo "==> health"
ssh "$HOST" "cd $DIR && sleep 3 && docker compose exec -T api node -e \"fetch('http://127.0.0.1:8080/api/health').then(r=>r.json()).then(j=>console.log(j))\""
echo "done."
