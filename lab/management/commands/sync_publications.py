"""이미 운영 중인 DB에 seed의 논문 링크와 출판 제목 교정을 반영한다. 2026-10 서버 반영용.

load_notion은 데이터가 있으면 거부하므로(규칙 6) 운영 서버에는 이 명령을 쓴다.
관리자가 고친 내용은 건드리지 않는다:
  · 링크는 비어 있는 칸에만 넣는다
  · 제목은 '예전에 우리가 seed로 넣은 값 그대로'일 때만 바꾼다
논문은 원문(raw)으로 찾는다. raw는 아무도 고치지 않는 칸이라 순서가 바뀌어도 같은 논문을 찾는다.
여러 번 돌려도 안전하다.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from lab.models import Publication

# (예전에 seed에 넣었던 표기, 출판본 표기). 출판된 제목에 오타가 있어 출판본대로 되돌린 것
PUBLISHED_TITLES = [
    ("Improving MOT", "Improvnig MOT"),   # DOI 10.9717/kmms.2024.27.12.1567
]


class Command(BaseCommand):
    help = "seed의 논문 링크·출판 제목 교정을 기존 DB에 반영한다 (빈 값만 채움, 관리자 수정분 보존)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 무엇이 바뀔지만 출력")

    def handle(self, *args, dry_run, **opts):
        seed = json.loads((settings.BASE_DIR / "seed/content/publications.json").read_text(encoding="utf-8"))
        links = titles = kept = missing = 0

        with transaction.atomic():
            for p in seed:
                found = list(Publication.objects.filter(kind=p["kind"], raw=p["raw"])[:2])
                if len(found) != 1:
                    missing += 1
                    self.stderr.write(self.style.WARNING(f"못 찾음({len(found)}건): {p['text'][:60]}"))
                    continue
                obj, changed = found[0], []

                if p.get("link"):
                    if obj.doi_url:
                        kept += obj.doi_url != p["link"]   # 관리자가 다른 링크를 넣어 둔 것
                    else:
                        obj.doi_url = p["link"]
                        changed.append("doi_url")

                for ours, published in PUBLISHED_TITLES:
                    if published in p["text"] and obj.text == p["text"].replace(published, ours):
                        obj.text = p["text"]
                        changed.append("text")

                if changed:
                    links += "doi_url" in changed
                    titles += "text" in changed
                    self.stdout.write(f"  + {', '.join(changed):12} {obj.text[:60]}")
                    if not dry_run:
                        obj.save(update_fields=changed)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(f"\n링크 채움 {links} · 제목 교정 {titles} · 관리자 링크 유지 {kept} · 못 찾음 {missing}")
        self.stdout.write(f"현재 링크 있는 논문: {Publication.objects.exclude(doi_url='').count()} / {Publication.objects.count()}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run 이므로 저장하지 않았습니다"))
