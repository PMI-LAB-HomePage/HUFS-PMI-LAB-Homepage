#!/bin/sh
# SQLite + media/ 를 날짜별 폴더로 백업하고 30일 지난 것은 지운다.
# cron (pmilab 사용자):  0 4 * * *  /srv/pmilab/app/deploy/backup.sh
# 서버 밖 사본은 별도로: 이 스크립트 뒤에 rsync 등으로 BACKUP_DIR 을 외부로 복사할 것.
set -eu
APP=/srv/pmilab/app
BACKUP_DIR=${BACKUP_DIR:-/srv/pmilab/backup}
DEST="$BACKUP_DIR/$(date +%F)"
mkdir -p "$DEST"

# 실행 중인 DB도 안전하게 복사 (sqlite3 CLI 없이 파이썬 표준 라이브러리 사용)
python3 -c 'import sqlite3, sys; sqlite3.connect(sys.argv[1]).backup(sqlite3.connect(sys.argv[2]))' \
  "$APP/db.sqlite3" "$DEST/db.sqlite3"
tar -czf "$DEST/media.tar.gz" -C "$APP" media

find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +
