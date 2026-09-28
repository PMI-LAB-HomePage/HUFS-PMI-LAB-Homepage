import tempfile

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Member

PAGES = ["home", "members", "publications", "research", "projects", "gallery", "news", "awards", "resources"]


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LoadNotionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_refuses_when_data_exists(self):
        with self.assertRaises(CommandError):
            call_command("load_notion")

    def test_public_pages_render_and_hide_emails(self):
        emails = [e for e in Member.objects.values_list("email", flat=True) if e]
        for name in PAGES:
            res = self.client.get(reverse(name))
            self.assertEqual(res.status_code, 200, name)
            for e in emails:
                self.assertNotIn(e, res.content.decode(), name)

    def test_admin_pages_render(self):
        self.client.force_login(User.objects.create_superuser("admin", "", "pw"))
        for model in ["sitesetting", "member", "publication", "news", "galleryevent", "research", "resource", "award", "project"]:
            self.assertEqual(self.client.get(f"/admin/lab/{model}/").status_code, 200, model)
        self.assertEqual(self.client.get(f"/admin/lab/member/{Member.objects.first().pk}/change/").status_code, 200)
        self.assertEqual(self.client.get("/admin/lab/sitesetting/add/").status_code, 403)  # 단일 레코드


class StripMarkdownTest(TestCase):
    """노션 본문 정리 규칙. Export 원본은 저장소 밖이라 enrich_notion 전체는 테스트하지 않는다."""

    def test_keeps_text_drops_attachments(self):
        from lab.management.commands.enrich_notion import strip_markdown

        self.assertEqual(strip_markdown("## 제목\n\n**굵게** 본문"), "제목\n\n굵게 본문")
        # 첨부 파일 링크·이미지는 본문이 아니다
        self.assertEqual(strip_markdown("[10-2507855-특허증.pdf](x.pdf)"), "")
        self.assertEqual(strip_markdown("![Untitled](a.png)\n\n1.mp4 형식이 아닌 문장"), "1.mp4 형식이 아닌 문장")
        # 일반 링크는 문구를 남긴다
        self.assertEqual(strip_markdown("자세한 내용은 [여기](http://x)"), "자세한 내용은 여기")
