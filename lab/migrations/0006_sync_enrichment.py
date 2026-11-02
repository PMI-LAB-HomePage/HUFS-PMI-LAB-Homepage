"""운영 DB에 빠져 있던 노션 보강분과 새 논문 링크 17건을 넣는다 (2026-11-03).

enrich_notion은 로컬에서만 돌아서 실서버에는 소식 본문·사진, 논문 PDF, 교수 CV, 연구 설명, 모집 본문이 없었다.
빈 칸에만 넣으므로 관리자 수정분은 그대로다. 새 DB는 비어 있어 아무것도 안 한다 — 그때는 load_notion이 넣는다.
"""
from django.db import migrations


def forward(apps, schema_editor):
    from lab.seed_sync import sync_enrichment, sync_publications

    Publication = apps.get_model("lab", "Publication")
    if Publication.objects.exists():
        sync_publications(Publication)
        sync_enrichment(apps.get_model)


class Migration(migrations.Migration):
    dependencies = [("lab", "0005_sync_publication_links")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
