# PMI Lab @ HUFS 홈페이지

한국외국어대학교 컴퓨터공학부 **PMI(Pattern Recognition & Machine Intelligence) Lab** 홈페이지.
기존 Notion 페이지를 Django 기반 자체 서버로 옮긴다. 관리자가 웹 화면에서 멤버·논문·소식·갤러리를
직접 등록·수정할 수 있게 하는 것이 목적이다.

- 주소: https://pmi.hufs.ac.kr (예정) · 기존 `lab.hufs.ac.kr/pmi`는 여기로 연결
- 구성: Docker Compose — Caddy → Gunicorn → Django(서버 렌더링) → SQLite

## 문서

| 문서 | 내용 |
|---|---|
| [CLAUDE.md](CLAUDE.md) | 작업 규칙 · 현재 상태 · 다음 할 일 (AI 작업자는 이것부터) |
| [docs/PROJECT.md](docs/PROJECT.md) | 배경 · 결정 이력 · 회의 결과 |
| [docs/DATA.md](docs/DATA.md) | 데이터 구조 · 적재 규칙 · 알려진 오류 |
| [docs/SERVER.md](docs/SERVER.md) | 서버 정보 · 배포 절차 (배포 담당자용) |

## 구조

```
config/        Django 설정
lab/           모델 · 관리자 · 뷰 · 템플릿 · 정적 파일 · 적재 명령
seed/          노션에서 옮긴 초기 데이터 (JSON + 이미지·PDF·영상)
compose.yaml   운영 구성 (caddy · web 컨테이너 2개)
Dockerfile     web 컨테이너 이미지
deploy/        Caddyfile · entrypoint.sh · backup.sh · DEPLOY.md
docs/          문서
```

로컬 개발은 Docker 없이 venv로 한다. 아래 그대로 하면 된다.
서버 배포만 Docker Compose를 쓴다 (`docs/SERVER.md`).

## 로컬 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py load_notion        # seed/ 데이터 최초 적재 (데이터가 있으면 거부)
python manage.py enrich_notion      # 노션 Export로 PDF·본문 보강 (로컬 전용, 빈 값만 채움)
python manage.py createsuperuser
python manage.py runserver          # http://localhost:8000/admin
python manage.py test lab           # 적재·페이지·관리자 스모크 테스트
```
