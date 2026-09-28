# DEPLOY.md — 이 폴더 파일 설치법

전체 순서(보안 설정 → 앱 → 웹서버 → 운영)는 `docs/SERVER.md` 4절. 이 문서는 그중 `deploy/` 파일을 어디에 두는지만 적는다.
경로는 모두 `/srv/pmilab/app`(저장소), `/srv/pmilab/venv`(가상환경) 기준.

| 파일 | 설치 위치 | 명령 |
|---|---|---|
| `pmilab.service` | `/etc/systemd/system/` | `sudo systemctl daemon-reload && sudo systemctl enable --now pmilab` |
| `Caddyfile` | `/etc/caddy/Caddyfile` | `sudo systemctl reload caddy` |
| `backup.sh` | 그대로 두고 cron 등록 | `sudo -u pmilab crontab -e` → `0 4 * * * /srv/pmilab/app/deploy/backup.sh` |

## 확인
```bash
systemctl status pmilab                 # active (running)
curl -I http://127.0.0.1:8000/          # 200
journalctl -u caddy -n 50               # 인증서 발급 로그
curl -I https://pmi.hufs.ac.kr/media/   # Caddy가 media를 직접 서빙하는지
```

## 주의
- `.env`: `SECRET_KEY` 새로 생성, `DEBUG=0`, `ALLOWED_HOSTS=pmi.hufs.ac.kr`. DEBUG=0이면 `change-me` 키로는 기동이 거부된다.
- Caddy(`caddy` 사용자)가 `staticfiles/`·`media/`를 읽을 수 있어야 한다.
  `useradd -m`이 만든 `/srv/pmilab`이 750이면 `sudo chmod 755 /srv/pmilab` 필요.
- 백업은 서버 안에만 있으면 디스크 고장 시 같이 사라진다. 최소 1곳은 서버 밖으로 복사할 것 (방법 미정 — 배포 담당자 결정).
- `load_notion`은 최초 1회만. 이후엔 데이터가 있으면 스스로 거부한다.
