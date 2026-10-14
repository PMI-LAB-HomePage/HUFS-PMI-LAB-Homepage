"""seed의 논문 링크·출판 제목 교정을 기존 DB에 반영한다 — 손으로 다시 돌리고 싶을 때용.

평소에는 배포 때 데이터 마이그레이션 0005가 DB마다 한 번 자동으로 돌린다.
이 명령은 무엇이 바뀔지 미리 보거나(--dry-run) 다시 맞추고 싶을 때 쓴다. 여러 번 돌려도 안전하다.
로직은 lab/seed_sync.py.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from lab.models import Publication
from lab.seed_sync import sync_publications


class Command(BaseCommand):
    help = "seed의 논문 링크·출판 제목 교정을 기존 DB에 반영한다 (빈 값만 채움, 관리자 수정분 보존)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="저장하지 않고 무엇이 바뀔지만 출력")

    def handle(self, *args, dry_run, **opts):
        with transaction.atomic():
            c = sync_publications(Publication, write=self.stdout.write)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(f"\n링크 채움 {c['links']} · 제목 교정 {c['titles']} · "
                          f"관리자 링크 유지 {c['kept']} · 못 찾음 {c['missing']}")
        self.stdout.write(f"현재 링크 있는 논문: {Publication.objects.exclude(doi_url='').count()} "
                          f"/ {Publication.objects.count()}")
        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run 이므로 저장하지 않았습니다"))
