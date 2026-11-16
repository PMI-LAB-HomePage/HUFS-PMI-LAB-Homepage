# SERVER.md — 서버 정보와 배포 절차

배포 담당자가 이 문서만 보고 서버를 구축·운영할 수 있도록 쓴 문서다.
코드 쪽 설정 파일(Caddyfile, systemd unit, 백업 스크립트)은 `deploy/`에 둔다.

---

## 1. 전체 구조

```
방문자
  ├─▶ lab.hufs.ac.kr/pmi ──(전산실이 리다이렉트)──▶ https://pmi.hufs.ac.kr
  └─▶ https://pmi.hufs.ac.kr
              │ A 레코드 (전산실이 등록)
              ▼
        연구실 서버 PC (Ubuntu, 공인 IP) — Docker Compose
          caddy 컨테이너 :80 :443     HTTPS 자동 발급·갱신, /static /media 직접 서빙
            └▶ web 컨테이너 :8000     Gunicorn → Django (호스트에 열지 않음)
                 └▶ ./data/           db.sqlite3 + media/   ← 백업 대상은 이 폴더 하나
```

**컨테이너 두 개가 전부다.** `compose.yaml` · `Dockerfile` · `deploy/` 만 보면 된다.
데이터는 이미지 안에 없다. 전부 호스트의 `./data`에 있고, 그래서 **백업은 폴더 복사**다.

- `lab.hufs.ac.kr`은 **공대 연구실 공용 도메인**이다. 여기의 DNS 변경은 절대 요청하지 않는다.
- 공인 IP만으로는 HTTPS 인증서를 받을 수 없어서 `pmi.hufs.ac.kr`이 필요하다.
  Let's Encrypt는 도메인에만 발급하고, 발급·갱신 검증이 80번으로 들어오므로 80·443을 함께 연다.

## 2. 서버 PC

```
호스트명     juneyonglee-titanxp
OS          Ubuntu
위치        공학관 423호
용도        웹서버 전용 (GPU 연구 용도 종료 확정)

인터페이스   enp2s0f1   ← 사용 중인 유선 포트
MAC         88:D7:F6:D5:C6:9D
현재 IP     220.67.128.37   ← 공인 IP로 보임. 고정 여부 전산실 확인 필요
(enp2s0f0   88:D7:F6:D5:C6:9C  — 미연결, 사용 안 함)
```

> ⚠ 랜선을 다른 포트로 옮기지 말 것. MAC이 바뀌어 방화벽 신청을 다시 해야 한다. 포트에 표시해 둘 것.

**현재 열려 있는 포트 (2026-09-28 확인)**
```
외부 노출   15232  SSH       ← 기본 22가 아님. 이 설정 유지
           7071   AnyDesk   ← 공개 전 종료
localhost  39855 containerd · 631 cupsd · 53 systemd-resolved   (외부에서 안 보임)
```
Docker 컨테이너 2개(tensorflow-gpu, ultralytics) — 모두 중지 상태. ultralytics에 8888 매핑이 남아 있음.

## 3. 전산실(정보전략팀) 협의 결과

| 항목 | 결과 |
|---|---|
| 네임서버 외부 위임 | 불가 (대학 DNS·보안정책) |
| 공인 IP + 80/443 | **가능** — 첨부 신청서 작성 후 회신 |
| 도메인 `pmi.hufs.ac.kr` | **사용 가능** |
| DNS 레코드 설정 | 신청서 전달 시 반나절 내 적용 |
| `lab.hufs.ac.kr/pmi` 연결 변경 | 정보전략팀이 처리(반나절). 구축 완료 후 연락. hufs-admin 계정 불필요 |
| 백신 | **설치 의무** → Ubuntu는 ClamAV로 갈음 가능한지 확인 요청 중 |
| 정기 취약점 점검 | 대상 아님 (학과 자산) |
| 보안 사고 | 정보전략팀으로 즉시 연락 |
| 금지 | 불법·유해정보, 해킹, 저작권 침해, 학교 명예 훼손 용도 → 도메인·IP 강제 회수 및 학칙 처벌 |

**실질적인 위험은 우리가 위반하는 경우가 아니라 서버가 뚫려 제3자가 우리 IP를 악용하는 경우다**
(스팸 발송·공격 경유지). 책임은 연구실에 온다. 아래 보안 설정을 웹서버보다 먼저 할 것.

### 공인 IP 신청서 기재값
```
사용 목적     연구실 홈페이지 운영 (웹서버)
소속          컴퓨터공학부 PMI Lab · 지도교수 최재영
담당자        (배포 담당자 이름 · 연락처 · 이메일)
설치 위치     공학관 423호
기기 MAC      88:D7:F6:D5:C6:9D
사용 포트     80, 443
도메인        pmi.hufs.ac.kr
운영체제      Ubuntu Server
```
회신에 함께 물을 것: ① 220.67.128.37이 고정 할당인지 ② 이 IP에 80/443 인바운드 개방 가능한지
(아니면 새 IP 발급인지) ③ Ubuntu에서 ClamAV 설치로 백신 요건 충족 가능한지.

## 4. 배포 절차 — 순서 엄수

### 4-1. 공개 전 정리
```bash
sudo systemctl disable --now anydesk        # 원격 접속은 SSH(15232)로 대체
docker ps -a                                 # 연구용으로 남아 있던 컨테이너 확인
docker rm 2f2906ab1ad0 9406bd292658          # tensorflow-gpu · ultralytics. 필요 없으면 제거
```
> ⚠ 이건 **이 프로젝트를 올리기 전에** 남아 있던 옛 컨테이너를 치우는 단계다.
> 배포 후에는 `docker rm`을 함부로 쓰지 말 것 — 우리 `web`·`caddy`가 같이 지워진다.
> 정지는 `docker compose down`, 정리는 `docker system prune -f`를 쓴다.

### 4-2. 보안 설정 — 웹서버 설치보다 먼저
```bash
sudo apt update && sudo apt upgrade -y

# 방화벽 — ⚠ SSH가 15232번이다. 이걸 먼저 허용하지 않고 enable하면 원격 접속이 영구히 끊긴다
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 15232/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose

# SSH 키 인증 — 키로 접속되는 것을 확인한 뒤에만 비밀번호 로그인을 끈다
#   /etc/ssh/sshd_config :  PasswordAuthentication no  ·  PermitRootLogin no
sudo systemctl restart ssh

sudo apt install -y fail2ban unattended-upgrades clamav clamav-daemon
sudo dpkg-reconfigure -plow unattended-upgrades
```
fail2ban의 sshd jail 포트를 15232로 맞출 것 (`/etc/fail2ban/jail.local`의 `[sshd] port = 15232`).

> ⚠ **ufw는 Docker가 공개한 포트를 막지 못한다.** Docker가 iptables의 `DOCKER` 체인에 직접
> 규칙을 넣어서 ufw를 건너뛴다. 즉 `compose.yaml`의 `ports:`에 적은 포트는 ufw 설정과 **무관하게**
> 밖에서 열린다. 우리는 80·443만 공개하므로 결과는 같지만, 이 사실을 모르면
> "ufw로 막았으니 안전하다"고 잘못 판단하게 된다.
> **규칙: 호스트에 노출할 포트는 `compose.yaml`의 `ports:`로만 결정한다.**
> `web`을 `ports:`가 아니라 `expose:`로 둔 것도 이 때문이다 — 8000번은 밖에서 안 보인다.
> 확인: `sudo ss -tlnp | grep -E ':(80|443|8000)\b'` 와 학교 밖 네트워크에서 `curl`.

### 4-3. 외부 접속 확인
전산실 방화벽이 열렸는지 **학교 밖 네트워크**(휴대폰 데이터 등)에서 확인한다.
80/443에 아직 아무것도 안 떠 있으면 "연결 거부"가 정상이고, "시간 초과"면 학교 방화벽이 아직 막혀 있는 것.

### 4-4. DNS 요청
전산실에 `pmi.hufs.ac.kr  A  <확정된 공인 IP>` 등록 요청. 확인: `dig +short pmi.hufs.ac.kr`

### 4-5. Docker 설치
```bash
sudo apt install -y git ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker compose version        # v2가 나와야 한다
```

> ⚠ **`docker-compose`(하이픈)가 아니라 `docker compose`(공백)** 다. 예전 v1 문법은 쓰지 않는다.

### 4-6. 애플리케이션 기동
```bash
sudo git clone <저장소 주소> /srv/pmilab/app
cd /srv/pmilab/app

cp .env.example .env
# .env 를 열어 SECRET_KEY 새로 생성, DEBUG=0, ALLOWED_HOSTS=pmi.hufs.ac.kr 로 고친다
#   SECRET_KEY 생성:  docker run --rm python:3.13-slim python -c "import secrets;print(secrets.token_urlsafe(50))"
# SQLITE_PATH·MEDIA_ROOT 는 건드리지 않는다 — compose.yaml이 넣어 준다

sudo docker compose up -d --build
sudo docker compose ps             # web·caddy 둘 다 running
sudo docker compose logs -f web    # migrate·collectstatic 후 gunicorn 기동 확인
```
컨테이너가 뜰 때마다 `migrate`와 `collectstatic`이 자동으로 돈다(`deploy/entrypoint.sh`).
여러 번 돌려도 안전하다.

### 4-6-1. 최초 1회만 — 데이터 적재와 관리자 계정
```bash
sudo docker compose exec web python manage.py load_notion
sudo docker compose exec web python manage.py createsuperuser
```
`load_notion`은 **데이터가 있으면 스스로 거부한다.** 재배포·재시작 때 다시 돌리지 않는다.
적재 후 출력되는 건수를 `docs/DATA.md` 5절의 기대 건수와 대조할 것.

### 4-6-2. 확인
```bash
curl -I https://pmi.hufs.ac.kr/                    # 200
curl -s https://pmi.hufs.ac.kr/robots.txt          # Sitemap 주소가 https://pmi.hufs.ac.kr 인지
curl -s https://pmi.hufs.ac.kr/sitemap.xml | head  # <loc>가 https://pmi.hufs.ac.kr/... 인지
sudo docker compose logs caddy                     # 인증서 발급 로그
```
브라우저에서 `https://pmi.hufs.ac.kr` 자물쇠와 `/admin` 로그인을 확인한다.

robots.txt·sitemap.xml의 주소는 **요청의 Host 헤더로 만들어진다.** Caddy가 Host를 그대로
넘기므로 보통 맞지만, 여기서 `127.0.0.1`이나 `localhost`가 보이면 프록시 설정을 확인할 것.

### 4-7. 운영 설정
```
백업       ./data 폴더 하나가 전부다. deploy/backup.sh + cron (매일 04:00)
             0 4 * * *  /srv/pmilab/app/deploy/backup.sh
           서버 안에만 둔다 (2026-09-29 결정). 아래 "백업 범위" 참고
자동 기동   compose의 restart: unless-stopped + docker 서비스 자동 시작이면 재부팅 후 자동으로 뜬다
             sudo systemctl enable docker
             재부팅해서 실제로 뜨는지 한 번 확인할 것
모니터링    UptimeRobot 등 무료 서비스로 5분 간격 점검, 다운 시 담당자 알림
정전        UPS · BIOS "전원 복구 시 자동 켜짐" 설정
```

#### 백업 범위 — 알고 받아들인 위험 (2026-09-29 결정)

백업을 **서버 밖으로 보내지 않기로 했다.** 그래서 이렇게 된다.

| 상황 | 결과 |
|---|---|
| 실수로 지움 · 잘못 수정 | **복구된다.** 최대 하루치만 잃는다 |
| SQLite 파일 깨짐 | **복구된다** |
| 디스크 고장 · 서버 도난 · 화재 | **전부 사라진다.** 백업도 같은 디스크에 있다 |

마지막 줄이 실제 위험이다. 연구실 사진 158장과 그동안 쌓은 기록이 한 번에 없어진다.
**다만 완전히 처음부터는 아니다** — 노션에서 옮겨온 초기 데이터는 저장소의 `seed/`에 있고
GitHub에도 올라가 있다. `load_notion`으로 다시 넣으면 **2026-09 시점까지는 되돌아간다.**
잃는 것은 그 이후에 관리자 화면에서 추가한 내용이다.

나중에 마음이 바뀌면 방법은 많다. 돈도 거의 안 든다.
```
가장 쉬움   USB 외장하드를 꽂아 두고 backup.sh 끝에 cp 한 줄 추가
그다음      rsync로 다른 PC(예: 연구실 다른 컴퓨터)에 매일 복사
클라우드    rclone 으로 구글 드라이브 등에 올리기 (학교 계정 용량으로 충분하다)
```
`./data`가 54MB 정도라 어느 방법이든 부담이 없다.

### 4-8. 전환
내부 검토 끝나면 정보전략팀에 연락 → `lab.hufs.ac.kr/pmi`를 `https://pmi.hufs.ac.kr`로 연결(반나절).
노션 사이트는 1~2개월 유지 후 정리 — 문제 생기면 연결을 되돌릴 수 있게.

## 5. 업데이트 — 자동 (2026-10-14부터)

**GitHub `main`에 push하면 10분 안에 실서버에 반영된다.** 서버가 10분마다 GitHub를 확인해서
새 커밋이 있을 때만 백업 → 받기 → 다시 빌드 → 점검을 한다 (`deploy/auto-update.sh`).

### 5-1. 처음 한 번만 설치

```bash
cd /srv/pmilab/app

# ① 서버가 비밀번호 없이 GitHub에서 받을 수 있는지 확인 (cron은 사람 없이 돈다)
sudo git fetch origin main && echo OK
#    비밀번호를 묻거나 실패하면 → 배포 키(SSH)를 쓰도록 원격 주소를 바꾼다
#    sudo git remote set-url origin git@github.com:PMI-LAB-HomePage/HUFS-PMI-LAB-Homepage.git
#    "dubious ownership" 오류가 나면 → sudo git config --global --add safe.directory /srv/pmilab/app

# ② 스크립트 받기 (이 단계에서는 사이트가 아직 안 바뀐다)
sudo git pull --ff-only

# ③ 첫 실행 — 지금 커밋까지 배포된다
sudo ./deploy/auto-update.sh
#    "배포 완료"가 나오면 성공. 브라우저에서 https://pmi.hufs.ac.kr 확인

# ④ 10분마다 자동으로
sudo crontab -e
#    맨 아래에 한 줄 추가:
#    */10 * * * * flock -n /tmp/pmilab-update.lock /srv/pmilab/app/deploy/auto-update.sh >> /srv/pmilab/auto-update.log 2>&1
```

### 5-2. 평소에 볼 것

```bash
tail -n 20 /srv/pmilab/auto-update.log      # 배포한 기록만 남는다 (새 커밋이 없으면 아무것도 안 쓴다)
cat /srv/pmilab/app/.deployed               # 지금 운영 중인 커밋
```

| 로그에 이게 보이면 | 뜻 | 할 일 |
|---|---|---|
| `배포 완료` | 정상 | 없음 |
| `실패 … 되돌림 완료` | 새 코드가 안 떠서 **이전 버전으로 자동 복구**됨 | 코드 담당에게 알림. 같은 커밋은 다시 시도하지 않고, 다음 커밋이 오면 다시 시도한다 |
| `중단: 서버의 로컬 변경과 충돌` | 서버에서 직접 고친 파일이 있다 | `git status`로 확인 후 정리. 스크립트는 덮어쓰지 않는다 |
| `경고: 되돌린 뒤에도 응답하지 않음` | 사람이 봐야 함 | `docker compose logs web` |

- 깨진 코드가 올라가면 **최대 약 2분** 사이트가 내려갔다가 이전 버전으로 돌아온다(점검을 기다리는 시간).
- 배포할 때마다 `deploy/backup.sh`로 먼저 백업한다.
- 잠시 멈추려면 crontab의 그 줄 앞에 `#`. 손으로 바로 반영하려면 `sudo ./deploy/auto-update.sh`.
- 2026-10-14 로컬 Docker에서 시험함: 첫 설치 · 새 커밋 없음 · 깨진 커밋(자동 복구) · 같은 커밋 재시도 안 함 · 고친 커밋 재배포.

### 5-3. 데이터도 바뀌는 업데이트

`git pull`은 코드만 바꾼다. 이미 데이터가 들어 있는 서버 DB를 고쳐야 할 때는 **데이터 마이그레이션**으로 만든다.
컨테이너가 뜰 때 `migrate`가 돌아서 **DB마다 정확히 한 번** 자동으로 반영되므로 따로 할 일이 없다.
`load_notion`은 절대 다시 돌리지 않는다 — 관리자가 고친 내용이 날아간다(명령도 거부한다).

| 날짜 | 마이그레이션 | 무엇 |
|---|---|---|
| 2026-10-14 | `0005_sync_publication_links` | 논문 링크 83건 · Improvnig 출판 제목. 빈 칸만 채우고 관리자 수정분 보존 |
| 2026-11-03 | `0006_sync_enrichment` | 논문 링크 17건 추가 · 소식 본문 22건·사진·링크 · 논문 PDF 14건 · 교수 CV · 연구 설명 · 모집 본문. 빈 칸만 채움 |
| 2026-11-16 | `0007_replace_lab_photos` | PMI 연구환경 이미지 10장을 사용자 제공 사진 7장(001~007)으로 교체. 이전 파일은 보존하며 본문·영상·다른 항목은 유지 |

미리 보고 싶으면: `sudo docker compose exec web python manage.py sync_publications --dry-run`

## 6. 자주 쓰는 명령
```bash
sudo docker compose ps                                  # 상태
sudo docker compose logs -f web                         # 앱 로그
sudo docker compose logs -f caddy                       # 인증서·프록시 로그
sudo docker compose restart caddy                       # Caddyfile 고친 뒤
sudo docker compose exec web python manage.py shell     # Django 셸
sudo docker compose down                                # 정지 (데이터는 ./data에 남는다)
sudo docker system prune -f                             # 안 쓰는 이미지 정리
```

## 7. 문제가 생기면
| 증상 | 확인할 것 |
|---|---|
| 502 Bad Gateway | `docker compose logs web` — 앱이 죽었거나 아직 뜨는 중 |
| 인증서 발급 실패 | 80번이 밖에서 열려 있는지. `docker compose logs caddy` |
| 정적 파일 404 | `docker compose exec web ls /app/staticfiles` — collectstatic이 돌았는지 |
| 업로드한 사진이 안 보임 | `ls ./data/media` — 권한(컨테이너 uid 10001)이 맞는지 |
| DB가 비어 보임 | `ls -l ./data/db.sqlite3` — 볼륨이 제대로 붙었는지 |
| 재부팅 후 안 뜸 | `systemctl is-enabled docker` |
