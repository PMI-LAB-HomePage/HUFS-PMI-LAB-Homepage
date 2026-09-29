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
        연구실 서버 PC (Ubuntu, 공인 IP)
          Caddy :80 :443        HTTPS 자동 발급·갱신, /static /media 직접 서빙
            └▶ Gunicorn :8000   (localhost만)
                 └▶ Django  →  SQLite 파일 + media/
```

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
docker ps -a                                 # 중지된 컨테이너 확인 후
docker rm 2f2906ab1ad0 9406bd292658          # 필요 없으면 제거
```

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

### 4-3. 외부 접속 확인
전산실 방화벽이 열렸는지 **학교 밖 네트워크**(휴대폰 데이터 등)에서 확인한다.
80/443에 아직 아무것도 안 떠 있으면 "연결 거부"가 정상이고, "시간 초과"면 학교 방화벽이 아직 막혀 있는 것.

### 4-4. DNS 요청
전산실에 `pmi.hufs.ac.kr  A  <확정된 공인 IP>` 등록 요청. 확인: `dig +short pmi.hufs.ac.kr`

### 4-5. 애플리케이션
```bash
sudo apt install -y python3-venv git
sudo useradd -r -m -d /srv/pmilab pmilab
sudo -u pmilab git clone <저장소 주소> /srv/pmilab/app
cd /srv/pmilab/app
sudo -u pmilab python3 -m venv /srv/pmilab/venv
sudo -u pmilab /srv/pmilab/venv/bin/pip install -r requirements.txt
sudo -u pmilab cp .env.example .env        # SECRET_KEY 새로 생성, DEBUG=0, ALLOWED_HOSTS=pmi.hufs.ac.kr
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py migrate
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py collectstatic --noinput
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py load_notion     # 최초 1회만
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py createsuperuser
```
이후 `deploy/`의 systemd unit 설치 → `systemctl enable --now` → 재부팅 후 자동 기동 확인.

### 4-6. 웹서버
Caddy 설치 후 `deploy/Caddyfile`을 `/etc/caddy/Caddyfile`로. 인증서 자동 발급 확인
(`journalctl -u caddy`). 브라우저에서 `https://pmi.hufs.ac.kr` 자물쇠 확인.

### 4-6-1. 확인
```bash
curl -I https://pmi.hufs.ac.kr/                    # 200
curl -s https://pmi.hufs.ac.kr/robots.txt          # Sitemap 주소가 https://pmi.hufs.ac.kr 인지
curl -s https://pmi.hufs.ac.kr/sitemap.xml | head  # <loc>가 https://pmi.hufs.ac.kr/... 인지
```
robots.txt·sitemap.xml의 주소는 **요청의 Host 헤더로 만들어진다.** Caddy가 Host를 그대로
넘기므로 보통 맞지만, 여기서 `127.0.0.1`이나 `localhost`가 보이면 리버스 프록시 설정을 확인할 것.

### 4-7. 운영 설정
```
백업       SQLite 파일 + media/ 를 매일 복사 (deploy/backup.sh + cron). 최소 1곳은 서버 밖으로
모니터링    UptimeRobot 등 무료 서비스로 5분 간격 점검, 다운 시 담당자 알림
정전        UPS · BIOS "전원 복구 시 자동 켜짐" 설정
```

### 4-8. 전환
내부 검토 끝나면 정보전략팀에 연락 → `lab.hufs.ac.kr/pmi`를 `https://pmi.hufs.ac.kr`로 연결(반나절).
노션 사이트는 1~2개월 유지 후 정리 — 문제 생기면 연결을 되돌릴 수 있게.

## 5. 업데이트 (배포 이후)
```bash
cd /srv/pmilab/app && sudo -u pmilab git pull
sudo -u pmilab /srv/pmilab/venv/bin/pip install -r requirements.txt
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py migrate
sudo -u pmilab /srv/pmilab/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart pmilab
```
`load_notion`은 다시 돌리지 않는다 — 관리자에서 고친 내용이 날아갈 수 있다(명령 자체도 데이터가 있으면 거부함).
