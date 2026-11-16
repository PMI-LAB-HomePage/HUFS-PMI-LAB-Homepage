"""사용자가 제공한 연구실 사진 7장으로 연구환경 이미지만 교체한다."""
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import migrations


def forward(apps, schema_editor):
    Resource = apps.get_model("lab", "Resource")
    ResourceMedia = apps.get_model("lab", "ResourceMedia")
    alias = schema_editor.connection.alias
    resources = list(Resource.objects.using(alias).filter(title_ko="PMI 연구환경"))
    if not resources:
        return  # 새 DB는 load_notion이 최신 seed로 채운다
    if len(resources) != 1:
        raise RuntimeError("PMI 연구환경 항목이 중복되어 사진 교체를 중단합니다.")

    # 파일이 빠졌으면 기존 사진을 지우기 전에 중단한다.
    folder = settings.BASE_DIR / "seed/assets/img/resources/lab-20261116"
    photos = [(f"{i:02}.webp", (folder / f"{i:02}.webp").read_bytes()) for i in range(1, 8)]
    resource = resources[0]
    ResourceMedia.objects.using(alias).filter(resource_id=resource.pk, kind="image").delete()
    for order, (name, data) in enumerate(photos):
        photo = ResourceMedia(resource_id=resource.pk, kind="image", order=order)
        photo.file.save(name, ContentFile(data), save=False)
        photo.save(using=alias)
    # 이전 이미지 파일은 보존한다. 관리자에서 올린 다른 항목과 영상은 그대로 둔다.


class Migration(migrations.Migration):
    dependencies = [("lab", "0006_sync_enrichment")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
