#!/bin/sh
# ./data (SQLite + media) 를 날짜별로 백업하고 30일 지난 것은 지운다.
#   cron:  0 4 * * *  /srv/pmilab/app/deploy/backup.sh
#
# ⚠ 이 스크립트는 서버 안에만 복사한다. 디스크가 죽으면 백업도 같이 사라진다.
#    최소 한 곳은 서버 밖으로 보낼 것 (rsync·클라우드 등 — 방법 미정, docs/SERVER.md 4-7).
set -eu
APP=$(cd "$(dirname "$0")/.." && pwd)
BACKUP_DIR=${BACKUP_DIR:-$APP/backup}
DEST="$BACKUP_DIR/$(date +%F)"
mkdir -p "$DEST"

# 실행 중에도 안전하게 복사한다. 컨테이너 안에서 sqlite3 백업 API를 쓴다
docker compose -f "$APP/compose.yaml" exec -T web \
  python -c 'import sqlite3; sqlite3.connect("/data/db.sqlite3").backup(sqlite3.connect("/data/backup.tmp"))'
mv "$APP/data/backup.tmp" "$DEST/db.sqlite3"

tar -czf "$DEST/media.tar.gz" -C "$APP/data" media

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
