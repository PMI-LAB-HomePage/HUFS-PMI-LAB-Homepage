"""seed/ → DB + media/ 최초 적재. 규칙은 docs/DATA.md 4절.

데이터가 이미 있으면 거부한다. --reset을 줬을 때만 비우고 다시 넣는다 (CLAUDE.md 규칙 6).
"""
import csv
import json
import re
import shutil
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from lab.models import (
    Award, AwardImage, GalleryEvent, GalleryImage, Member, News, Project, Publication,
    Research, ResearchGroup, ResearchMedia, Resource, ResourceMedia, SiteSetting,
)

SEED = settings.BASE_DIR / "seed"
MODELS = [SiteSetting, Member, Publication, News, GalleryEvent, ResearchGroup, Research,
          Resource, Award, Project]

# 연구 11건 → 노션 홈의 연구 분야 5분류. 이름만으로는 자동으로 못 맞춰서(예: "Supervised,
# Unsupervised Image Inpainting" ↔ "Deep Image Restoration") 사람이 판단해 적어 둔 표다.
# 바꾸려면 여기를 고치거나 관리자 화면에서 연구별 "연구 분야"를 바꾸면 된다.
RESEARCH_GROUP = {
    "Deep Domain Adaptation": "Deep Face Recognition",
    "Deep Attention Learning": "Deep Face Recognition",
    "3D-2D Cascaded Deep Networks for Video Face Recognition": "Deep Face Recognition",
    "Deep Ensemble Network": "Deep Face Recognition",
    "Deep Image Restoration": "Deep Learning for Image Generation",
    "Deep Image Translation": "Deep Learning for Image Generation",
    "Object Detection and Tracking": "Deep Object Detection and Tracking",
    "Object Re-Identification": "Deep Object Detection and Tracking",
    "LSTM Ensemble for Time-series Forecasting": "Deep Learning for Time-series Prediction",
    "3D DCNN and ConvLSTM for Predicting fine dust": "Deep Learning for Time-series Prediction",
    "Facial Emotion Recognition": "Demo Videos",
}
MEDIA_DIRS = ["site", "members", "publications", "gallery", "research", "resources", "awards"]

# 위쪽이 우선
ROLE_MAP = [
    ("PMI Lab Director", Member.Role.PROFESSOR),
    ("Ph.D Student", Member.Role.PHD),
    ("Master Student", Member.Role.MS),
    ("MS. Graduate", Member.Role.MS),
    ("학부생연구원", Member.Role.UNDERGRAD),
    ("BS. Graduate", Member.Role.UNDERGRAD),
    ("연구실 연구원", Member.Role.RESEARCHER),
]
ROLE_TITLES = {t for t, _ in ROLE_MAP}

EXPECTED = {
    SiteSetting: 1, Member: 29, Publication: 119, News: 24, GalleryEvent: 38,
    ResearchGroup: 5, Research: 11, Resource: 5, Award: 7, Project: 16,
}


def has_ko(s):
    return bool(re.search("[가-힣]", s or ""))


def ko_en(field, value):
    """한글이 있으면 _ko, 없으면 _en."""
    return {f"{field}_ko" if has_ko(value) else f"{field}_en": value or ""}


def name_key(s):
    return re.sub(r"[\W_]", "", s).lower()


def clean_email(s):
    # 노션 Export가 "mailto:" 또는 "https://app.notion.com"을 앞에 붙여 둔 경우가 있다
    return s.removeprefix("mailto:").removeprefix("https://app.notion.com").strip()


class Command(BaseCommand):
    help = "seed/의 노션 데이터를 DB와 media/로 최초 적재한다"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="기존 데이터를 모두 지우고 다시 적재 (관리자 수정분도 사라짐)")

    def handle(self, *args, reset, **opts):
        existing = {m._meta.verbose_name: m.objects.count() for m in MODELS if m.objects.exists()}
        if existing and not reset:
            raise CommandError(f"이미 데이터가 있어 중단합니다: {existing}. 지우고 다시 넣으려면 --reset")

        with transaction.atomic():
            if reset:
                for m in MODELS:
                    m.objects.all().delete()
                for d in MEDIA_DIRS:
                    shutil.rmtree(Path(settings.MEDIA_ROOT) / d, ignore_errors=True)
            self.load_site()
            self.load_members()
            self.load_publications()
            self.load_news()
            self.load_gallery()
            self.load_research_groups()
            self.load_media_items("research", Research, ResearchMedia, "research")
            self.assign_research_groups()
            self.load_media_items("resources", Resource, ResourceMedia, "resource")
            self.load_awards()
            self.load_projects()
        self.report()

    # ---- helpers ----

    def seed_json(self, name):
        return json.loads((SEED / "content" / f"{name}.json").read_text(encoding="utf-8"))

    def attach(self, field, rel_path):
        path = SEED / rel_path
        if not path.exists():
            self.stderr.write(self.style.WARNING(f"파일 없음: {rel_path}"))
            return
        with path.open("rb") as f:
            field.save(path.name, File(f), save=False)

    def parse_date(self, s, context):
        if not s:
            return None
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s.strip())
        if m:
            return date(int(m[3]), int(m[1]), int(m[2]))
        m = re.fullmatch(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", s.strip())
        if m:
            return date(int(m[1]), int(m[2]), int(m[3]))
        self.stderr.write(self.style.WARNING(f"날짜 해석 실패 ({context}): {s!r}"))
        return None

    # ---- loaders ----

    def load_site(self):
        s = self.seed_json("site")["site"]
        obj = SiteSetting(**{k: s.get(k, "") for k in [
            "lab_name_ko", "lab_name_en", "lab_short", "email", "address_ko", "address_en",
            "recruit_notice_ko", "recruit_notice_en"]})
        self.attach(obj.home_image, "assets/img/home/home/01.webp")
        obj.save()

    def member_photos(self):
        """asset_map.csv의 members·home 섹션에서 사람 이름 → 첫 사진 경로."""
        photos = {}
        with (SEED / "asset_map.csv").open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row["종류"] == "image" and row["섹션"] in ("members", "home") and row["제목"] != "home":
                    photos.setdefault(name_key(row["제목"]), row["새경로"])
        return photos

    def load_members(self):
        prof = self.seed_json("site")["professor"]
        photos = self.member_photos()
        for m in self.seed_json("members"):
            status = m["status"]
            role = next((r for t, r in ROLE_MAP if t in status), Member.Role.OTHER)
            career = m["career_after"] or ", ".join(s for s in status if s not in ROLE_TITLES)
            emails = [clean_email(e) for e in m["emails"]]
            obj = Member(
                role=role,
                status_text=", ".join(status),
                email=emails[0] if emails else "",
                research_interests=", ".join(m["research_interest"]),
                is_current=m["is_current"],
                career_after=career,
                order=m["order"],
                import_note=json.dumps(
                    {"sources": m["sources"], "name_variants": m["name_variants"], "emails": m["emails"]},
                    ensure_ascii=False, indent=1),
                **{"name_ko" if has_ko(m["name"]) else "name_en": m["name"]},
            )
            if role == Member.Role.PROFESSOR:
                obj.name_ko = prof["name_ko"]
                obj.email = prof["email"]
                obj.bio_en = "\n\n".join(prof["bio_en"])
            photo = next((photos[k] for k in map(name_key, [m["name"], *m["name_variants"]]) if k in photos), None)
            if photo:
                self.attach(obj.photo, photo)
            obj.save()

    def load_publications(self):
        Publication.objects.bulk_create(
            Publication(kind=p["kind"], text=p["text"], raw=p["raw"], year=p["year"], order=p["seq"])
            for p in self.seed_json("publications"))

    def load_news(self):
        for n in self.seed_json("news"):
            News.objects.create(
                date=self.parse_date(n["date"], n["title"]),
                tag=n["tags"][0].lower() if n["tags"] else News.Tag.NEWS,
                link=n["link"],
                **ko_en("title", n["title"]),
                **ko_en("body", n["body"]),
            )

    def load_gallery(self):
        for i, g in enumerate(self.seed_json("gallery")):
            ev = GalleryEvent.objects.create(
                date=self.parse_date(g["date"], g["title"]),
                date_end=self.parse_date(g["date_end"], g["title"]),
                location=g["location"],
                is_public=g["is_public"],
                order=i,
                **ko_en("title", g["title"]),
                **ko_en("description", g["note"]),
            )
            for j, path in enumerate(g["images"]):
                img = GalleryImage(event=ev, order=j)
                self.attach(img.image, path)
                img.save()

    def load_research_groups(self):
        for i, g in enumerate(self.seed_json("site")["research_groups"]):
            ResearchGroup.objects.create(order=i, **ko_en("title", g["title"]))

    def assign_research_groups(self):
        groups = {g.title_en or g.title_ko: g for g in ResearchGroup.objects.all()}
        for obj in Research.objects.all():
            title = obj.title_en or obj.title_ko
            group_title = RESEARCH_GROUP.get(title)
            if group_title is None:
                self.stderr.write(self.style.WARNING(f"연구 분야 미배정: {title}"))
                continue
            obj.group = groups[group_title]
            obj.save(update_fields=["group"])

    def load_media_items(self, name, model, media_model, fk):
        for r in self.seed_json(name):
            obj = model.objects.create(subtitle=r["subtitle"], order=r["order"],
                                       is_public=r.get("is_public", True), **ko_en("title", r["title"]))
            for j, path in enumerate(r["images"]):
                med = media_model(order=j, kind="video" if path.lower().endswith(".mp4") else "image", **{fk: obj})
                self.attach(med.file, path)
                med.save()

    def load_awards(self):
        for i, a in enumerate(self.seed_json("awards")):
            aw = Award.objects.create(
                date=self.parse_date(a["date"], a["title"]),
                recipients=", ".join(a["tags"]),
                order=i,
                **ko_en("title", a["title"]),
            )
            for j, path in enumerate(a["images"]):
                img = AwardImage(award=aw, order=j)
                self.attach(img.image, path)
                img.save()

    def load_projects(self):
        Project.objects.bulk_create(
            Project(text=p["text"], raw=p["raw"], year=p["year"], order=p["order"])
            for p in self.seed_json("projects"))

    def report(self):
        ok = True
        for model, want in EXPECTED.items():
            got = model.objects.count()
            ok &= got == want
            self.stdout.write(f"{'OK ' if got == want else 'XX '} {model._meta.verbose_name}: {got} (기대 {want})")
        extra = {
            "현재 멤버 (기대 6)": Member.objects.filter(is_current=True).count(),
            "사진 있는 멤버": Member.objects.exclude(photo="").count(),
            "사진 있는 갤러리 (기대 35)": GalleryEvent.objects.filter(images__isnull=False).distinct().count(),
            "비공개 (갤러리 1 · 자료실 3)": GalleryEvent.objects.filter(is_public=False).count() + Resource.objects.filter(is_public=False).count(),
            "갤러리 사진": GalleryImage.objects.count(),
            "연구 영상": ResearchMedia.objects.filter(kind="video").count(),
            "연구 분야 미배정 (기대 0)": Research.objects.filter(group=None).count(),
        }
        for kind, label in Publication.Kind.choices:
            extra[f"논문 {kind}"] = Publication.objects.filter(kind=kind).count()
        for k, v in extra.items():
            self.stdout.write(f"    {k}: {v}")
        self.stdout.write(self.style.SUCCESS("적재 완료") if ok else self.style.ERROR("기대 건수와 다름 — 확인 필요"))
