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
