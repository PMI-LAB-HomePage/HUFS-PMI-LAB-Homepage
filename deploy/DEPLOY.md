# DEPLOY.md — 이 폴더 파일이 하는 일

전체 순서(보안 설정 → Docker → 앱 → 확인 → 운영)는 `docs/SERVER.md` 4절.
이 문서는 **파일별 역할과 고칠 때 주의할 점**만 적는다.

구성은 컨테이너 두 개다. 설정은 저장소 루트의 `compose.yaml`과 `Dockerfile`에 있다.

```
caddy 컨테이너  :80 :443   HTTPS 자동 발급·갱신 · /static /media 직접 서빙
  └▶ web 컨테이너 :8000    Gunicorn → Django   (호스트에 열지 않음)
       └▶ ./data/          db.sqlite3 + media/   ← 백업 대상
```

| 파일 | 하는 일 | 고칠 때 |
|---|---|---|
| `Caddyfile` | 도메인 · HTTPS · 정적 파일 · 프록시 | 고친 뒤 `docker compose restart caddy` (읽기 전용 마운트라 재빌드 불필요) |
| `entrypoint.sh` | 컨테이너 기동마다 `migrate` + `collectstatic` | 고친 뒤 `docker compose up -d --build` |
| `backup.sh` | `./data`를 날짜별로 복사, 30일 보관 | cron 등록: `0 4 * * * /srv/pmilab/app/deploy/backup.sh` |

## 데이터는 전부 `./data` 안에 있다

```
data/
├── db.sqlite3      DB
└── media/          관리자가 올린 사진·PDF
```

이미지를 다시 빌드해도, 컨테이너를 지웠다 만들어도 이 폴더는 남는다.
**백업은 이 폴더를 복사하면 끝이다.** 옮길 때도 이 폴더만 가져가면 된다.

`staticfiles`는 백업 대상이 아니다 — 기동할 때마다 `collectstatic`이 다시 만든다.

## 주의

- **`.env`는 커밋하지 않는다.** `.env.example`을 복사해서 서버에서 만든다.
  `SECRET_KEY` 새로 생성, `DEBUG=0`, `ALLOWED_HOSTS=pmi.hufs.ac.kr`.
  `DEBUG=0`인데 `SECRET_KEY`가 `change-me`이면 앱이 기동을 거부한다.
- **`SQLITE_PATH`·`MEDIA_ROOT`는 `.env`에 넣지 않는다.** `compose.yaml`이 넣어 준다.
  `.env`에 잘못 넣으면 데이터가 볼륨 밖(컨테이너 안)에 생겨서 재빌드 때 사라진다.
- **`ports:`에 적은 포트는 ufw로 막히지 않는다.** Docker가 iptables를 직접 건드린다.
  호스트에 열 포트는 `compose.yaml`의 `ports:`로만 결정한다 (`docs/SERVER.md` 4-2).
- **`caddy_data` 볼륨을 지우지 말 것.** 발급받은 인증서가 들어 있다.
  지우면 재발급을 받는데 Let's Encrypt 발급 한도에 걸릴 수 있다.
- `load_notion`은 **최초 1회만.** 데이터가 있으면 명령 자체가 거부하지만, `--reset`은 쓰지 말 것.
- 백업이 서버 안에만 있으면 디스크 고장 때 같이 사라진다.
  **최소 한 곳은 서버 밖으로 보낼 것** — 방법은 아직 안 정해졌다(배포 담당자 결정).
