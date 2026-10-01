#!/bin/sh
# Deploy the latest code on the server: pull, build, migrate, restart. Safe to run again.
set -e
cd "$(dirname "$0")/.."
BRANCH="${1:-phase-2}"
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
git reset --quiet --hard "origin/$BRANCH"
echo "Deploying $(git log --oneline -1)"
COMPOSE="docker compose -f deploy/docker-compose.prod.yml"
nice -n 10 $COMPOSE build --quiet
$COMPOSE run --rm --no-deps api python manage.py migrate --noinput
$COMPOSE up -d --remove-orphans
sleep 4
$COMPOSE ps --format "table {{.Service}}\t{{.State}}\t{{.Status}}"
curl -fsS http://127.0.0.1:8020/api/health && echo
