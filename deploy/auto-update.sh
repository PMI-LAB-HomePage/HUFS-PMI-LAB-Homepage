#!/bin/sh
# 자동 업데이트 — GitHub main에 새 커밋이 있으면 백업 → 받기 → 다시 빌드 → 점검.
# 점검에 실패하면 이전 버전으로 되돌리고, 같은 커밋은 다시 시도하지 않는다(새 커밋이 오면 다시 시도).
#
# cron (root, 10분마다). 설치·확인 방법은 docs/SERVER.md 5절.
#   */10 * * * * flock -n /tmp/pmilab-update.lock /srv/pmilab/app/deploy/auto-update.sh >> /srv/pmilab/auto-update.log 2>&1
#
# 새 커밋이 없으면 아무것도 출력하지 않고 끝난다 — 로그에는 배포한 기록만 남는다.
# 데이터베이스 변경(마이그레이션)은 컨테이너가 뜰 때 entrypoint.sh가 돌린다.
set -eu
APP=$(cd "$(dirname "$0")/.." && pwd)
cd "$APP"

log() { echo "$(date '+%F %T') $*"; }
short() { echo "$1" | cut -c1-7; }

# 사이트가 실제로 응답하는지 web 컨테이너 안에서 확인한다 (Caddy·HTTPS와 무관하게)
HOST=$(grep '^ALLOWED_HOSTS=' .env | cut -d= -f2 | cut -d, -f1)
healthy() {
    i=0
    while [ $i -lt 30 ]; do
        docker compose exec -T web python -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/', headers={'Host': '$HOST'}), timeout=5)" \
            >/dev/null 2>&1 && return 0
        i=$((i + 1)); sleep 3
    done
    return 1
}

git fetch -q origin main
TARGET=$(git rev-parse origin/main)
DEPLOYED=$(cat .deployed 2>/dev/null || echo none)

[ "$TARGET" = "$DEPLOYED" ] && exit 0                               # 할 일 없음
[ "$TARGET" = "$(cat .deploy-failed 2>/dev/null || true)" ] && exit 0   # 이미 실패한 커밋

# 되돌릴 곳 = 마지막으로 정상 배포된 커밋 (첫 설치라 기록이 없으면 지금 커밋)
if [ "$DEPLOYED" != none ]; then PREV=$DEPLOYED; else PREV=$(git rev-parse HEAD); fi
log "배포 시작: $(short "$PREV") → $(short "$TARGET")  $(git log -1 --format=%s "$TARGET")"

# 실행 중인 컨테이너가 있을 때만 백업이 된다 (첫 설치 때는 건너뜀)
if docker compose ps --status running --services 2>/dev/null | grep -qx web; then
    ./deploy/backup.sh && log "백업 완료"
fi

# 서버에서 직접 고친 파일이 있으면 여기서 멈춘다 — 덮어쓰지 않는다. 로그를 보고 사람이 정리할 것
if ! git merge --ff-only -q "$TARGET"; then
    log "중단: 서버의 로컬 변경과 충돌해 코드를 받을 수 없음. 'git status'로 확인 필요"
    exit 1
fi

if docker compose up -d --build --quiet-pull >/dev/null 2>&1 && healthy; then
    echo "$TARGET" > .deployed
    rm -f .deploy-failed
    log "배포 완료: $(short "$TARGET")"
    exit 0
fi

# 실패 — 이전 버전으로 되돌린다
log "실패: 빌드 또는 점검 실패. $(short "$PREV")로 되돌린다"
echo "$TARGET" > .deploy-failed
git reset -q --hard "$PREV"
docker compose up -d --build --quiet-pull >/dev/null 2>&1 || true
if healthy; then
    log "되돌림 완료: $(short "$PREV")로 운영 중. $(short "$TARGET")는 다음 커밋이 올 때까지 다시 시도하지 않음"
else
    log "경고: 되돌린 뒤에도 사이트가 응답하지 않음. 'docker compose logs web' 확인 필요"
fi
exit 1
