# DATA.md — 데이터 구조와 적재 규칙

노션에서 옮겨온 초기 데이터(`seed/`)의 형태, 목표 모델, 적재 시 변환 규칙, 알려진 오류.

---

## 1. seed 구조

```
seed/
├── content/                 노션 Export CSV·페이지를 정리한 JSON (UTF-8)
│   ├── site.json            사이트 기본값 · 교수 약력 · 연구 분류 (노션 본문에서 수동 추출)
│   ├── members.json         29명  (현재 9 · 동문 20)
│   ├── publications.json   119건
│   ├── news.json            24건
│   ├── gallery.json         38건
│   ├── research.json        11건
│   ├── resources.json        5건
│   ├── awards.json           7건
│   └── projects.json        16건
├── asset_map.csv            노션 원본 파일 ↔ seed 경로 매핑 (272행)
└── assets/                  최적화된 파일 (97MB)
    ├── img/{gallery,research,awards,resources,members,home}/<slug>/NN.webp
    │        gallery는 <slug>/thumb/NN.webp (600px) 별도
    ├── pdf/{publication,home}/*.pdf
    └── video/research/*.mp4
```

- **JSON 안의 파일 경로는 모두 `seed/` 기준 상대경로**다 (`assets/img/gallery/...`).
- 이미지: WebP, 긴 변 최대 1600px, EXIF 회전 보정 완료. 영상: H.264, 폭 최대 1280px.
- PDF는 원본 화질 유지, 파일명만 ASCII로 정리. 중복 1건 제거.
- 노션 원본 전체(458MB)는 저장소 밖 `../04_노션Export/`에 있다. 보강 작업에만 쓴다.

## 2. JSON 필드

```
members.json
  name              대표 표기 (영문 "Min Su, Jo" 형식 또는 한글)
  name_variants     노션에 나온 모든 표기
  emails            [..]  여러 목록에서 모은 것
  status            [..]  노션 Status 다중선택 원문 — 직함과 진로가 섞여 있음 (아래 4절)
  research_interest [..]
  career_after      동문의 현재 소속 ("(주)스트라드비젼" 등)
  is_current        현재 멤버 여부 (홈 인라인 또는 Members 페이지의 Current 목록에 있으면 true)
  sources           ["home_inline","members_page","alumni"] 중 출처
  order

publications.json
  kind              intl_journal | intl_conference | dom_journal | dom_conference | patent
  kind_label        노션 페이지 제목
  seq               원본 페이지에서의 번호
  raw               마크다운 원문 (굵게 표시 등 보존)
  text              마크다운 제거한 정리본
  year              본문에서 추출한 연도 (119건 전부 추출됨)
  pdf, doi          빈 값 — 보강 대상

news.json          title · date · tags[] · body("") · link("")
gallery.json       title · date · date_end · location · note · images[] · is_public
research.json      title · subtitle · images[] (이미지+영상 섞임, 확장자로 구분) · order
resources.json     title · subtitle · images[] · order
awards.json        title · date · tags[] · images[]
projects.json      seq · raw · text · year · order
site.json          site{...} · professor{...} · research_groups[...]
```

## 3. 목표 모델 (`lab/models.py`)

**화면에 보이는 텍스트는 `_ko`/`_en` 쌍.** 표시할 때 `ko or en`. 모든 목록형 모델에 `order`, `is_public`.

```
SiteSetting    (단일 레코드)
  lab_name_ko/en · lab_short · email · address_ko/en · recruit_notice_ko/en · home_image(홈 대표 사진)
  ※ 상단 메뉴 구성은 만들지 않았다 (2026-09-28 결정). `03_작업메모/06_동적기능_범위확정.md`에는
    관리 항목으로 적혀 있으나, ① 메뉴는 페이지를 새로 만들 때만 바뀌고 페이지 추가는 코드 작업이라
    메뉴만 따로 관리해서 얻는 게 없다 ② 2단계 시안에서 메뉴 구조를 다시 짠다 ③ 관리자가 전부 숨기면
    사이트 이동이 막힌다. 2단계에서 시안을 보고 다시 판단한다. 지금은 `lab/templates/lab/base.html`에 고정.

Member
  name_ko · name_en · role (professor|phd|ms|undergrad|researcher|other)
  status_text (노션 직함 원문) · email · research_interests
  photo · cv(PDF) · bio_ko/en · is_current · career_after
  order · is_public · import_note (출처·표기 변형·이메일 전체 — 손실 방지용, 관리자에서 접어둠)

Publication
  kind · text · raw · year · pdf · doi_url · order · is_public
  ※ 저자·제목·학술지 분리는 2차 작업. 지금은 만들지 않는다

News + NewsImage(news, image, order)
  title_ko/en · date · tag (academic|recruit|patent|news) · body_ko/en · link · is_public

GalleryEvent + GalleryImage(event, image, order)
  title_ko/en · date · date_end · location · description_ko/en · is_public · order

Research + ResearchMedia(research, file, kind=image|video, order)
  title_ko/en · subtitle · description_ko/en · order · is_public

Resource + ResourceMedia(resource, file, kind, order)
  title_ko/en · subtitle · body_ko/en · order · is_public

Award + AwardImage(award, image, order)
  title_ko/en · date · recipients · order · is_public

Project
  text · raw · year · order · is_public
  ※ year는 정렬용. seed 값이 "2022-2027"의 끝 연도라서 year_start가 아니라 year로 둠
  ※ 역할·과제명·금액·발주처 분리는 2차 작업
```

## 4. 적재 규칙 (`load_notion`)

**안전장치:** DB에 해당 모델 데이터가 이미 있으면 **중단**한다. `--reset`을 줬을 때만 비우고 다시 넣는다.

**언어 배정:** 원본 텍스트에 한글이 있으면 `_ko`, 없으면 `_en`에 넣는다. 반대쪽은 빈 값.

**날짜 형식이 섞여 있다.**
```
news.json          "12/18/2024"          (MM/DD/YYYY)
gallery · awards   "2026년 2월 20일"      (YYYY년 M월 D일)
```
두 형식 모두 파싱. 실패하면 null로 두고 경고 출력 (멈추지 말 것).

**멤버 status 해석** — 다중선택에 직함과 진로가 섞여 있다.
```
직함 → role
  PMI Lab Director            professor
  Ph.D Student                phd
  Master Student, MS. Graduate  ms
  학부생연구원, BS. Graduate    undergrad
  연구실 연구원                 researcher
  (여러 개면 위쪽 우선)
진로 → career_after (비어 있을 때만)
  취업, 고려대학교 대학원
```
`status` 원문 전체는 `status_text`에, `sources`·`name_variants`·`emails` 전체는 `import_note`에 남긴다.

**이름:** 한글이면 `name_ko`, 아니면 `name_en`. 교수는 `site.json`의 professor로 `name_ko`·`bio_en` 채움.

**파일:** `seed/<경로>`를 Django `File`로 열어 모델 필드에 저장 → `media/` 아래로 복사된다.
research·resources의 `images`는 확장자가 `.mp4`면 `kind=video`.
저장 파일명은 `media/<종류>/<무작위 16자>.<확장자>` — 관리자가 한글 파일명을 올려도 ASCII로 저장된다(규칙 1).

**이메일:** 노션 Export가 붙인 `mailto:`·`https://app.notion.com` 접두어를 떼고 첫 번째를 `email`에 넣는다.
원문 전체는 `import_note`.

**멤버 사진:** `asset_map.csv`의 `members`·`home` 섹션에서 이름(`name`·`name_variants`)을 공백·구두점
제거 후 소문자로 비교해 첫 사진을 연결한다. 29명 전원 매칭됨.

**홈 대표 사진:** `assets/img/home/home/01.webp` → `SiteSetting.home_image`.

**태그:** news `Academic/Recruit/Patent/News` → 소문자 choice.

## 5. 기대 건수 (적재 후 대조)

```
SiteSetting 1 · Member 29 (현재 9) · Publication 119 · News 24
GalleryEvent 38 (이미지 있는 것 35) · Research 11 · Resource 5 · Award 7 · Project 16

Publication 종류별: intl_journal 43 · intl_conference 37 · dom_journal 18 · dom_conference 5 · patent 16
```

## 6. 보강 작업 (`enrich_notion`) — 완료 2026-09-28

`load_notion`만으로는 비는 것들을 노션 Export 원본에서 채운다. **Export(458MB)는 저장소 밖
`../04_노션Export/`에 있으므로 이 명령은 손성원 로컬에서 1회만 돌린다. 서버에서는 쓰지 않는다.**

```bash
python manage.py enrich_notion --dry-run     # 무엇이 바뀔지만 출력
python manage.py enrich_notion               # 적용
python manage.py enrich_notion --export <경로>   # Export 위치가 다를 때
```

**빈 값만 채운다.** 이미 값이 있으면 건너뛴다 — 관리자가 고친 내용을 덮어쓰지 않기 위해서다(규칙 6과 같은 취지).
그래서 여러 번 돌려도 안전하다(2회차는 "채움 0 · 건너뜀 32").

### 채운 것 (합계 32)

| 대상 | 건수 | 방법 |
|---|---|---|
| 논문 PDF | 13 | `Publication/<종류>/*.md`의 번호 항목 다음 줄 PDF 링크 → `asset_map.csv` |
| 특허증 | 1 | `10-2507855.pdf` → 본문에 등록번호가 든 특허 |
| 교수 CV | 1 | `jae-young-choi-cv-23-02.pdf` → `Member.cv` |
| 소식 본문 | 12 | `Lab News/*.md` 본문 |
| 소식 사진 | 2 | `asset_map.csv`의 `home` 섹션에서 제목이 같은 것 |
| 연구 설명 | 2 | `Research/*.md` 본문 |
| 자료실 본문 | 1 | `Resources/*.md` 본문 |

### 파싱하며 걸린 함정 — 고쳐 둠

1. **PDF 링크 파일명에 괄호가 있다** (`02_(5-2024-067).pdf`). `\(([^)]*)\)` 로 잡으면 5건을 놓친다.
   비탐욕 매칭(`\]\((.+?\.pdf)\)`)을 쓴다.
2. **소식 제목이 겹친다** (`[논문게재] 한국멀티미디어학회` 등 4쌍). 제목만으로 짝지으면 엉뚱한 본문이
   붙는다(17건 매칭 → 실제는 13건). **제목 + 날짜**로 맞춰야 한다.
3. **노션 Export 경로는 두 번 인코딩된 것이 섞여 있다.** `unquote`를 더 이상 안 바뀔 때까지 반복한다.
4. **본문에 첨부 파일 링크가 텍스트로 남는다** (`[10-2507855-특허증.pdf](...)`, `1.mp4`).
   링크 문구가 파일명 꼴이면 문구까지 버린다. 남는 글자가 없으면 본문 없음으로 친다.
5. **국제학회 md만 번호 형식이 다르다** (`[2]      ` — 첫 항목만 `1. `). 두 형식 다 인식한다.
   이 파일엔 PDF가 없어서 결과에는 영향이 없다.
6. **연구·자료실 페이지 대부분은 본문이 이미지뿐**이다. 그래서 11건 중 2건, 5건 중 1건만 텍스트가 있다.
   정상이다.

### 검증

논문 PDF는 파일명 속 연·월(`05_(2023-8-124)` → 2023년 8월)이 논문 서지의 연·월과 모두 일치했다.

## 7. 알려진 데이터 문제 — 임의 수정 금지, 교수님 확인 후

```
논문 오탈자     Improvnig→Improving · Setp.→Sept. · fro robust→for robust
               Cdoing→Coding · PLUS ONE→PLOS ONE · IEEE ACESS→ACCESS
문장 잘림       국제저널 43번 항목 끝이 "Citation: .pdf"로 끊김
번호 오류       노션 국내저널 페이지 번호가 3번 뒤 1번으로 되돌아감 (seq는 1~18로 재부여됨)
멤버           현재 9명은 세 목록의 합집합 — 실제와 다름. 손성원이 관리자에서 정리 예정
               조민수: 2024-12 환송회 기록 있음 → 재학 여부 확인
               이유진: 직함 "연구실 연구원" — 다른 표기와 불일치
갤러리          사진 없는 항목 3건 (ACM KDD 2024 · 2021 Sung-Tae Kim 세미나 · 2017 Prof. Choi 튜토리얼)
               내부 성격 항목("24년 정지민 감사편지" 등) — 공개 여부 판단 필요
               날짜 없는 항목 1건
수상            노션 원본의 빈 행 1개는 제외함 (8 → 7)
```

`Kyung Tae, Kim` / `Kyung-Tae, Kim`은 동일인으로 이미 병합됨.
