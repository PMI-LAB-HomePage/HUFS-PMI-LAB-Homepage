#!/bin/sh
# 컨테이너가 뜰 때마다 도는 것: 마이그레이션 + 정적 파일 수집.
# 둘 다 여러 번 돌려도 안전하다. load_notion·createsuperuser는 여기 넣지 않는다 —
# 최초 1회만 사람이 직접 실행한다 (docs/SERVER.md).
set -eu

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec "$@"
