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
  lab_name_ko/en · lab_short · email · address_ko/en · recruit_notice_ko/en

Member
  name_ko · name_en · role (professor|phd|ms|undergrad|researcher|other)
  status_text (노션 직함 원문) · email · research_interests
  photo · bio_ko/en · is_current · career_after
  order · is_public · import_note (출처·표기 변형·이메일 전체 — 손실 방지용, 관리자에서 접어둠)

Publication
  kind · text · raw · year · pdf · doi_url · order · is_public
  ※ 저자·제목·학술지 분리는 2차 작업. 지금은 만들지 않는다

News
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
  text · raw · year_start · order · is_public
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

**태그:** news `Academic/Recruit/Patent/News` → 소문자 choice.

## 5. 기대 건수 (적재 후 대조)

```
SiteSetting 1 · Member 29 (현재 9) · Publication 119 · News 24
GalleryEvent 38 (이미지 있는 것 35) · Research 11 · Resource 5 · Award 7 · Project 16

Publication 종류별: intl_journal 43 · intl_conference 37 · dom_journal 18 · dom_conference 5 · patent 16
```

## 6. 보강 작업 (선택 — 원본은 `../04_노션Export/`)

적재만으로는 비어 있는 것들. 노션 Export 원본을 읽어 채운다. `asset_map.csv`로 원본↔seed 경로를 찾는다.

**논문 PDF 연결 (13건 + 특허증 1)**
Export의 `Publication/<종류>/*.md`에서 번호 항목 바로 다음 줄의 `[파일명.pdf](...)` 링크가 그 항목의
첨부다. 파일명으로 `asset_map.csv`의 `제목`(원본 파일명)을 찾아 `새경로`를 연결한다.
`10-2507855-특허증.pdf`는 특허 "고속 연산이 가능한 딥러닝 신경망 장치(등록번호 10-2507855)"의 것.

**멤버 사진**
`asset_map.csv`의 섹션 `members`(동문 페이지들)와 `home`(홈 인라인 멤버 페이지들)에 사람 이름을
제목으로 한 사진 폴더가 있다. 이름 비교는 공백·구두점 제거 후 소문자로 (`Prof Jae Young, Choi` ↔
`Prof. Jae Young, Choi`). `home/home/01.webp`는 홈 대표 사진이지 멤버 사진이 아니다.

**교수 CV:** `assets/pdf/home/jae-young-choi-cv-23-02.pdf`.

**본문 텍스트:** 소식·연구·자료실 각 항목의 노션 페이지 본문(`*.md`)을 `body`/`description`으로.
맨 위 제목 줄과 `속성: 값` 줄은 제외.

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
