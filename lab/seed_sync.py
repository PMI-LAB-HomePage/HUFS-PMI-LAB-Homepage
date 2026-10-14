"""seed의 논문 링크·출판 제목 교정을 이미 운영 중인 DB에 반영하는 로직.

데이터 마이그레이션(0005)과 `manage.py sync_publications` 명령이 같이 쓴다.
관리자가 고친 내용은 건드리지 않는다:
  · 링크는 비어 있는 칸에만 넣는다
  · 제목은 '예전에 우리가 seed로 넣은 값 그대로'일 때만 바꾼다
논문은 원문(raw)으로 찾는다. raw는 아무도 고치지 않는 칸이라 순서가 바뀌어도 같은 논문을 찾는다.
"""
import json

from django.conf import settings

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
