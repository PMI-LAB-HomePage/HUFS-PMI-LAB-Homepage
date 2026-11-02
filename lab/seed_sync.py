"""seed의 논문 링크·출판 제목 교정·노션 보강분을 이미 운영 중인 DB에 반영하는 로직.

데이터 마이그레이션(0005·0006)과 `manage.py sync_publications` 명령이 같이 쓴다.
관리자가 고친 내용은 건드리지 않는다:
  · 링크는 비어 있는 칸에만 넣는다
  · 제목은 '예전에 우리가 seed로 넣은 값 그대로'일 때만 바꾼다
논문은 원문(raw)으로 찾는다. raw는 아무도 고치지 않는 칸이라 순서가 바뀌어도 같은 논문을 찾는다.
"""
import json
from collections import Counter

from django.conf import settings
from django.core.files import File

# (예전에 seed에 넣었던 표기, 출판본 표기). 출판된 제목에 오타가 있어 출판본대로 되돌린 것
PUBLISHED_TITLES = [
    ("Improving MOT", "Improvnig MOT"),   # DOI 10.9717/kmms.2024.27.12.1567
]


def sync_publications(Publication, write=lambda line: None):
    """Publication 모델 클래스를 받는다(마이그레이션은 과거 시점 모델을 넘기므로). 바뀐 건수를 돌려준다."""
    seed = json.loads((settings.BASE_DIR / "seed/content/publications.json").read_text(encoding="utf-8"))
    counts = {"links": 0, "titles": 0, "kept": 0, "missing": 0}

    for p in seed:
        found = list(Publication.objects.filter(kind=p["kind"], raw=p["raw"])[:2])
        if len(found) != 1:
            counts["missing"] += 1
            continue
        obj, changed = found[0], []

        if p.get("link"):
            if obj.doi_url:
                counts["kept"] += obj.doi_url != p["link"]   # 관리자가 다른 링크를 넣어 둔 것
            else:
                obj.doi_url = p["link"]
                changed.append("doi_url")

        for ours, published in PUBLISHED_TITLES:
            if published in p["text"] and obj.text == p["text"].replace(published, ours):
                obj.text = p["text"]
                changed.append("text")

        if changed:
            counts["links"] += "doi_url" in changed
            counts["titles"] += "text" in changed
            write(f"  + {', '.join(changed):12} {obj.text[:60]}")
            obj.save(update_fields=changed)
    return counts


def sync_enrichment(get_model, write=lambda line: None):
    """seed/content/enrich.json(소식 본문·사진, 논문 PDF, 교수 CV, 연구 설명, 모집 본문)을 빈 칸에만 넣는다.

    enrich_notion은 저장소 밖 노션 Export가 있어야 돌아서 운영 서버에서 쓸 수 없다. 그 결과만 seed로 옮겨 둔 것이다.
    get_model은 apps.get_model — 마이그레이션은 과거 시점 모델을 넘긴다. 제목이 바뀌었으면 관리자가 손댄 것이므로 건너뛴다.
    """
    seed = settings.BASE_DIR / "seed"
    data = json.loads((seed / "content/enrich.json").read_text(encoding="utf-8"))
    counts = Counter()

    def attach(field, rel):
        path = seed / rel
        if not path.exists():
            counts["missing"] += 1
            return False
        with path.open("rb") as f:
            field.save(path.name, File(f), save=False)
        return True

    def fill_body(obj, body):
        field = body["field"]
        if getattr(obj, f"{field[:-3]}_ko") or getattr(obj, f"{field[:-3]}_en"):
            return False
        setattr(obj, field, body["value"])
        obj.save(update_fields=[field])
        return True

    def by_title(objects, title):
        found = [o for o in objects if (o.title_ko or o.title_en) == title]
        return found[0] if len(found) == 1 else None

    News, NewsImage = get_model("lab", "News"), get_model("lab", "NewsImage")
    for n in data["news"]:
        obj = by_title(News.objects.filter(date=n["date"]), n["title"])
        if obj is None:
            counts["missing"] += 1
            continue
        if "body" in n and fill_body(obj, n["body"]):
            counts["news_bodies"] += 1
        if n.get("link") and not obj.link:
            obj.link = n["link"]
            obj.save(update_fields=["link"])
            counts["news_links"] += 1
        if n.get("images") and not obj.images.exists():
            for i, rel in enumerate(n["images"]):
                img = NewsImage(news=obj, order=i)
                if attach(img.image, rel):
                    img.save()
                    counts["news_images"] += 1

    Publication = get_model("lab", "Publication")
    for p in data["publications"]:
        found = list(Publication.objects.filter(kind=p["kind"], raw=p["raw"])[:2])
        if len(found) == 1 and not found[0].pdf and attach(found[0].pdf, p["pdf"]):
            found[0].save(update_fields=["pdf"])
            counts["pdfs"] += 1

    Member = get_model("lab", "Member")
    professor = Member.objects.filter(role="professor").first()
    if professor and not professor.cv and attach(professor.cv, data["professor_cv"]):
        professor.save(update_fields=["cv"])
        counts["cv"] += 1

    for key, name in [("research", "Research"), ("resources", "Resource")]:
        objects = list(get_model("lab", name).objects.all())
        for r in data[key]:
            obj = by_title(objects, r["title"])
            if obj is not None and fill_body(obj, r["body"]):
                counts[key] += 1

    write(f"  보강: {dict(counts)}")
    return counts
