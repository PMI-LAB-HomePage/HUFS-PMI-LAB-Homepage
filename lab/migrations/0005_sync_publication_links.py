"""운영 DB에 논문 링크 83건과 Improvnig 출판 제목을 넣는다 (2026-10-14).

배포하면 컨테이너가 migrate를 돌리므로 DB마다 정확히 한 번 자동으로 실행된다.
빈 링크 칸에만 넣고 관리자가 고친 서지는 건드리지 않는다 (lab/seed_sync.py).
새로 만든 DB는 아직 비어 있어 아무것도 안 한다 — 그때는 load_notion이 seed에서 링크까지 넣는다.

앞으로 운영 DB에 데이터를 고쳐 넣어야 할 때도 이렇게 데이터 마이그레이션으로 만든다 (CLAUDE.md).
"""
from django.db import migrations


def forward(apps, schema_editor):
    from lab.seed_sync import sync_publications

    Publication = apps.get_model("lab", "Publication")
    if Publication.objects.exists():
        sync_publications(Publication)


class Migration(migrations.Migration):
    dependencies = [("lab", "0004_alter_publication_doi_url")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
