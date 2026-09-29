import re
import tempfile

from django.utils.html import escape

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import GalleryEvent, Member, News, Publication

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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SeoAndErrorPageTest(TestCase):
    """검색 노출이 주 유입 경로라 sitemap·robots는 동작해야 한다."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_sitemap_lists_every_public_page(self):
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertEqual(self.client.get("/sitemap.xml").status_code, 200)
        for name in PAGES:
            self.assertIn(f"<loc>http://testserver{reverse(name)}</loc>", body, name)
        # 갤러리 목록 1 + 사진 있는 행사 35 (사진 없는 3건은 상세가 없다)
        self.assertEqual(body.count("<loc>http://testserver/gallery/"), 36)
        # 소식 상세는 본문이나 사진이 있는 것만. 여기선 enrich_notion을 돌리지 않아 목록 1개뿐이다
        self.assertEqual(body.count("<loc>http://testserver/news/"), 1)
        News.objects.filter(pk=News.objects.first().pk).update(body_ko="본문")
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertEqual(body.count("<loc>http://testserver/news/"), 2)

    def test_robots_allows_site_and_blocks_admin(self):
        res = self.client.get("/robots.txt")
        self.assertEqual(res["Content-Type"], "text/plain")
        self.assertIn("Disallow: /admin/", res.content.decode())
        self.assertIn("Sitemap: http://testserver/sitemap.xml", res.content.decode())

    def test_404_uses_site_design(self):
        res = self.client.get("/no-such-page/")
        self.assertEqual(res.status_code, 404)
        self.assertContains(res, "페이지를 찾을 수 없습니다", status_code=404)

    def test_500_renders_without_request_or_context(self):
        # 실제 500은 컨텍스트 프로세서·DB 없이 렌더된다. base.html을 상속하면 여기서 깨진다.
        from django.template.loader import render_to_string

        html = render_to_string("500.html")
        self.assertIn("일시적인 오류", html)
        self.assertNotIn("{{", html)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ListPageLogicTest(TestCase):
    """목록 화면이 사용자에게 거짓말하지 않는지."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_tab_counts_follow_the_search(self):
        # 검색 중인데 전체 건수를 보여주면, 탭을 눌렀을 때 그 숫자만큼 안 나온다
        res = self.client.get(reverse("publications"), {"q": "Ensemble"})
        shown = int(re.search(r'논문 · 특허 <span class="count">(\d+)', res.content.decode())[1])
        all_tab = int(re.search(r'>전체<span class="tab__count">(\d+)', res.content.decode())[1])
        self.assertEqual(shown, all_tab)
        self.assertLess(all_tab, Publication.objects.count())

    def test_publication_number_survives_filtering(self):
        # 번호는 그 종류 안에서의 고유 번호다. 검색·탭으로 걸러져도 다시 매기면 안 된다
        pub = Publication.objects.filter(kind="intl_journal").order_by("order").first()
        total = Publication.objects.filter(kind="intl_journal").count()
        expected = f'cite__num">{total - pub.order + 1}<'

        self.assertContains(self.client.get(reverse("publications")), expected)
        self.assertContains(self.client.get(reverse("publications"), {"type": "intl_journal"}), expected)
        res = self.client.get(reverse("publications"), {"q": pub.text.split()[-1]})
        self.assertContains(res, expected)

    def test_gallery_pager_points_backwards_in_time(self):
        events = list(GalleryEvent.objects.filter(is_public=True, date__isnull=False)[:3])
        body = self.client.get(reverse("gallery_detail", args=[events[1].pk])).content.decode()
        prev_url = re.search(r'<a href="([^"]+)"><span>← 이전</span>', body)[1]
        next_url = re.search(r'<a href="([^"]+)"><span>다음 →</span>', body)[1]
        self.assertEqual(prev_url, reverse("gallery_detail", args=[events[2].pk]))  # 더 과거
        self.assertEqual(next_url, reverse("gallery_detail", args=[events[0].pk]))  # 더 최신
        self.assertLess(events[2].date, events[1].date)
