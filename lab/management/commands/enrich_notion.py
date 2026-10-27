"""노션 Export 원본을 읽어 `load_notion`이 채우지 못한 것을 보강한다. 규칙은 docs/DATA.md 6절.

Export 원본(458MB)은 저장소 밖에 있으므로 이 명령은 **손성원 로컬에서 1회만** 돌린다.
서버에서는 쓰지 않는다 (Export가 없다).

빈 값만 채운다. 이미 값이 있으면 건드리지 않는다 — 관리자가 고친 내용을 덮어쓰지 않기 위해서다
(AGENTS.md 규칙 6과 같은 취지).
"""
import csv
import json
import re
import urllib.parse
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lab.models import Member, News, NewsImage, Publication, Research, Resource

SEED = settings.BASE_DIR / "seed"
DEFAULT_EXPORT = settings.BASE_DIR.parent / "04_노션Export/개인 페이지 & 공유된 페이지/PMI Lab @ HUFS"

KINDS = {
    "Domestic Conferences": Publication.Kind.DOM_CONFERENCE,
    "Domestic Journals": Publication.Kind.DOM_JOURNAL,
    "International Conferences": Publication.Kind.INTL_CONFERENCE,
    "International Journal": Publication.Kind.INTL_JOURNAL,
    "Patents": Publication.Kind.PATENT,
}

# 노션 Export의 번호 항목: "1. 내용" 또는 국제학회의 "[2]      내용"
ITEM_RE = re.compile(r"^\s*(?:\d+\.|\[\d+\])\s+\S")
# 링크 대상에 괄호가 든 파일명이 있어서(`02_(5-2024-067).pdf`) 비탐욕 매칭을 쓴다
PDF_LINK_RE = re.compile(r"\]\((.+?\.pdf)\)", re.I)
PROP_RE = re.compile(r"^[A-Za-z가-힣 ]{1,20}:\s")
MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
MD_HEADING_RE = re.compile(r"^#+\s*", re.M)
# 링크 문구가 첨부 파일명이면 본문 텍스트가 아니다 ("1.mp4", "10-2507855-특허증.pdf")
FILENAME_RE = re.compile(r"^[\w .\-()가-힣]+\.(pdf|mp4|webp|png|jpe?g|docx?|pptx?)$", re.I)
PATENT_NO_RE = re.compile(r"10-?(\d{7})")


def unquote_all(s):
    """노션 Export 경로는 두 번 인코딩된 것이 섞여 있다."""
    while (d := urllib.parse.unquote(s)) != s:
        s = d
    return s


def norm(s):
    return re.sub(r"[\W_]", "", s or "").lower()


def strip_markdown(text):
    """본문에서 마크다운 문법을 걷어내고 읽을 수 있는 텍스트만 남긴다.

    첨부 파일(이미지·영상·PDF)은 본문이 아니라 파일이므로 문구까지 버린다. 남는 게 없으면 빈 문자열.
    """
    text = MD_IMAGE_RE.sub("", text)
    text = MD_LINK_RE.sub(lambda m: "" if FILENAME_RE.match(m[1].strip()) else m[1], text)
    text = MD_HEADING_RE.sub("", text)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text if re.search(r"[가-힣A-Za-z]", text) else ""


class Command(BaseCommand):
    help = "노션 Export에서 논문 PDF·CV·소식 사진·본문 텍스트를 보강한다 (빈 값만 채움)"

    def add_arguments(self, parser):
        parser.add_argument("--export", default=str(DEFAULT_EXPORT), help="노션 Export의 'PMI Lab @ HUFS' 폴더")
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 무엇이 바뀔지만 출력")

    def handle(self, *args, export, dry_run, **opts):
        self.export = Path(export)
        if not self.export.is_dir():
            raise CommandError(f"Export 폴더가 없습니다: {self.export}\n--export 로 경로를 지정하세요.")
        self.dry_run = dry_run
        self.filled = self.skipped = 0

        self.asset_map = self.load_asset_map()
        with transaction.atomic():
            self.enrich_publication_pdfs()
            self.enrich_patent_certificate()
            self.enrich_professor_cv()
            self.enrich_news()
            self.enrich_bodies("Research", Research, "description")
            self.enrich_bodies("Resources", Resource, "body")
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(f"\n채움 {self.filled} · 이미 값이 있어 건너뜀 {self.skipped}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run 이므로 저장하지 않았습니다"))

    # ---- helpers ----

    def load_asset_map(self):
        """(섹션, 정규화한 제목) → [새경로], 그리고 원본 파일명 → 새경로."""
        by_title, by_filename = {}, {}
        with (SEED / "asset_map.csv").open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["종류"].startswith("pdf"):
                    by_filename.setdefault(Path(unquote_all(row["원본"])).name, row["새경로"])
                elif row["종류"] == "image":
                    by_title.setdefault((row["섹션"], norm(row["제목"])), []).append(row["새경로"])
        return {"title": by_title, "filename": by_filename}

    def fill_file(self, obj, field, rel_path, label):
        if getattr(obj, field):
            self.skipped += 1
            return
        path = SEED / rel_path
        if not path.exists():
            self.stderr.write(self.style.WARNING(f"파일 없음: {rel_path}"))
            return
        with path.open("rb") as f:
            getattr(obj, field).save(path.name, File(f), save=not self.dry_run)
        self.filled += 1
        self.stdout.write(f"  + {label} ← {rel_path}")

    def fill_text(self, obj, field, value, label):
        """_ko/_en 중 한글 여부에 맞는 쪽을 채운다 (load_notion과 같은 규칙)."""
        suffix = "_ko" if re.search("[가-힣]", value) else "_en"
        name = field + suffix
        if getattr(obj, name) or getattr(obj, field + ("_en" if suffix == "_ko" else "_ko")):
            self.skipped += 1
            return
        setattr(obj, name, value)
        if not self.dry_run:
            obj.save(update_fields=[name])
        self.filled += 1
        self.stdout.write(f"  + {label} ({name}) {value[:50]!r}")

    def read_page(self, md):
        """노션 페이지 md → (제목, 속성dict, 본문)."""
        lines = md.read_text(encoding="utf-8").splitlines()
        title = lines[0].lstrip("#").strip()
        rest, props = lines[1:], {}
        while rest and (not rest[0].strip() or PROP_RE.match(rest[0])):
            line = rest.pop(0)
            if ":" in line and PROP_RE.match(line):
                k, v = line.split(":", 1)
                props[k.strip()] = v.strip()
        return title, props, strip_markdown("\n".join(rest))

    # ---- steps ----

    def enrich_publication_pdfs(self):
        self.stdout.write("논문 PDF")
        for label, kind in KINDS.items():
            md = next(self.export.glob(f"Publication/{label} *.md"), None)
            if md is None:
                self.stderr.write(self.style.WARNING(f"Export에 없음: Publication/{label}"))
                continue
            seq = 0
            for line in md.read_text(encoding="utf-8").splitlines():
                if ITEM_RE.match(line):
                    seq += 1
                    continue
                for target in PDF_LINK_RE.findall(line):
                    filename = Path(unquote_all(target)).name
                    rel = self.asset_map["filename"].get(filename)
                    pub = Publication.objects.filter(kind=kind, order=seq).first()
                    if rel is None or pub is None:
                        self.stderr.write(self.style.WARNING(f"연결 실패 {label} {seq}번: {filename}"))
                        continue
                    self.fill_file(pub, "pdf", rel, f"{label} {seq}번")

    def enrich_patent_certificate(self):
        """특허증 PDF는 Lab News 페이지에 붙어 있다. 등록번호로 해당 특허를 찾는다."""
        self.stdout.write("특허증")
        for filename, rel in self.asset_map["filename"].items():
            m = PATENT_NO_RE.search(filename)
            if not m or "publication" in rel:
                continue
            pub = next((p for p in Publication.objects.filter(kind=Publication.Kind.PATENT)
                        if m[1] in re.sub(r"\D", "", p.text)), None)
            if pub is None:
                self.stderr.write(self.style.WARNING(f"등록번호 {m[0]} 특허를 못 찾음: {filename}"))
                continue
            self.fill_file(pub, "pdf", rel, f"특허 {m[0]}")

    def enrich_professor_cv(self):
        self.stdout.write("교수 CV")
        rel = next((v for k, v in self.asset_map["filename"].items() if "cv" in k.lower()), None)
        prof = Member.objects.filter(role=Member.Role.PROFESSOR).first()
        if rel and prof:
            self.fill_file(prof, "cv", rel, str(prof))
        else:
            self.stderr.write(self.style.WARNING("CV 또는 교수 레코드를 찾지 못함"))

    def enrich_news(self):
        """소식은 제목이 겹치는 것이 4쌍 있어서 제목만으로는 안 되고 날짜까지 맞춘다."""
        self.stdout.write("소식 본문·사진")
        seed_news = json.load(open(SEED / "content/news.json", encoding="utf-8"))
        by_date = {}
        for md in self.export.glob("Lab News/*.md"):
            title, props, body = self.read_page(md)
            by_date[(norm(title), props.get("Date", ""))] = body

        for raw, obj in zip(seed_news, News.objects.order_by("id")):
            # seed 순서와 DB 생성 순서가 같다는 전제 — load_notion이 순서대로 만든다
            assert norm(raw["title"]) == norm(obj.title_ko or obj.title_en), f"소식 순서 어긋남: {raw['title']}"
            body = by_date.get((norm(raw["title"]), raw["date"]))
            if body:
                self.fill_text(obj, "body", body, str(obj)[:30])
            for i, rel in enumerate(self.asset_map["title"].get(("home", norm(raw["title"])), [])):
                if obj.images.exists():
                    self.skipped += 1
                    break
                img = NewsImage(news=obj, order=i)
                self.fill_file(img, "image", rel, f"사진 {obj}"[:40])
                if not self.dry_run:
                    img.save()

    def enrich_bodies(self, folder, model, field):
        self.stdout.write(f"{folder} 본문")
        bodies = {}
        for md in self.export.glob(f"{folder}/*.md"):
            title, _, body = self.read_page(md)
            if body:
                bodies[norm(title)] = body
        for obj in model.objects.all():
            body = bodies.get(norm(obj.title_ko or obj.title_en))
            if body:
                self.fill_text(obj, field, body, str(obj)[:30])
