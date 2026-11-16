import re
import tempfile
from pathlib import Path

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


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LabPhotoReplacementTest(TestCase):
    def test_replaces_only_environment_images_and_preserves_old_files(self):
        import importlib
        from types import SimpleNamespace
        from django.apps import apps
        from django.core.files.base import ContentFile
        from django.db import connection
        from .models import Resource, ResourceMedia

        env = Resource.objects.create(title_ko="PMI 연구환경", body_ko="관리자가 수정한 설명")
        old = ResourceMedia(resource=env)
        old.file.save("old.webp", ContentFile(b"old photo"))
        other = Resource.objects.create(title_ko="다른 자료")
        kept = ResourceMedia.objects.create(resource=other, file="resources/keep.webp")
        video = ResourceMedia.objects.create(resource=env, kind="video", file="resources/keep.mp4")

        forward = importlib.import_module("lab.migrations.0007_replace_lab_photos").forward
        forward(apps, SimpleNamespace(connection=connection))

        photos = list(env.media.filter(kind="image"))
        self.assertEqual([photo.order for photo in photos], list(range(7)))
        from django.conf import settings
        for i, photo in enumerate(photos, 1):
            expected = settings.BASE_DIR / f"seed/assets/img/resources/lab-20261116/{i:02}.webp"
            with photo.file.open("rb") as stored:
                self.assertEqual(stored.read(), expected.read_bytes())
        env.refresh_from_db()
        self.assertEqual(env.body_ko, "관리자가 수정한 설명")
        self.assertTrue(old.file.storage.exists(old.file.name))
        self.assertTrue(ResourceMedia.objects.filter(pk=kept.pk).exists())
        self.assertTrue(ResourceMedia.objects.filter(pk=video.pk).exists())


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

    def test_read_page_keeps_labeled_lines_as_body(self):
        # "논문제목: ..."을 속성으로 보고 버려서 소식 9건의 본문이 통째로 사라진 적이 있다
        from lab.management.commands.enrich_notion import Command

        with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8") as f:
            f.write("# 제목\n\nDate: 05/10/2022\nPatent: Academic\n\n논문제목: 어떤 논문\n\n논문저자: 홍길동\n")
            f.flush()
            title, props, body = Command().read_page(Path(f.name))
        self.assertEqual((title, props["Date"]), ("제목", "05/10/2022"))
        self.assertEqual(body, "논문제목: 어떤 논문\n\n논문저자: 홍길동")


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
        # 갤러리 목록 1 + 공개·사진 있는 행사 34
        # (사진 없는 3건은 상세가 없고, 감사편지 1건은 비공개다 — docs/DATA.md 7절)
        self.assertEqual(body.count("<loc>http://testserver/gallery/"), 35)
        # 소식은 목록 1 + 본문이나 사진이 있는 상세 22. 제목뿐인 상세 2건은 검색에 내보내지 않는다
        self.assertEqual(body.count("<loc>http://testserver/news/"), 23)
        empty = next(n for n in News.objects.all() if not (n.body_ko or n.body_en or n.images.exists()))
        News.objects.filter(pk=empty.pk).update(body_ko="본문")
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertEqual(body.count("<loc>http://testserver/news/"), 24)

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

    def test_project_years_are_marked_as_end_years(self):
        # 과제 연도는 끝나는 해다. 그냥 "2027"이면 미래 연도 과제처럼 보인다
        res = self.client.get(reverse("projects"))
        self.assertContains(res, "~2027")
        self.assertNotContains(res, '__year">2027<')

    def test_gallery_pager_points_backwards_in_time(self):
        events = list(GalleryEvent.objects.filter(is_public=True, date__isnull=False)[:3])
        body = self.client.get(reverse("gallery_detail", args=[events[1].pk])).content.decode()
        prev_url = re.search(r'<a href="([^"]+)"><span>← 이전</span>', body)[1]
        next_url = re.search(r'<a href="([^"]+)"><span>다음 →</span>', body)[1]
        self.assertEqual(prev_url, reverse("gallery_detail", args=[events[2].pk]))  # 더 과거
        self.assertEqual(next_url, reverse("gallery_detail", args=[events[0].pk]))  # 더 최신
        self.assertLess(events[2].date, events[1].date)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TypoCorrectionTest(TestCase):
    """오탈자는 화면용 text만 고쳤다. 원문 raw는 그대로여야 한다 (AGENTS.md 규칙 4)."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_display_text_is_corrected_but_raw_keeps_the_original(self):
        for typo in ["Setp.", "fro robust", "Cdoing", "PLUS ONE", "IEEE ACESS",
                     "Neual", "Citation: .pdf"]:
            self.assertFalse(Publication.objects.filter(text__contains=typo).exists(), typo)
            self.assertTrue(Publication.objects.filter(raw__contains=typo).exists(), typo)

    def test_published_title_typo_is_kept(self):
        # 학술지에 "Improvnig"로 출판됐다(DOI 10.9717/kmms.2024.27.12.1567).
        # 인용은 출판 기록과 같아야 하므로 고치지 않는다
        self.assertTrue(Publication.objects.filter(text__contains="Improvnig MOT").exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PublicationLinkTest(TestCase):
    """논문 링크: seed에서 적재되고, 화면에 나오고, 관리자에서 없는 것만 골라 채울 수 있어야 한다."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_links_are_loaded_and_rendered(self):
        linked = Publication.objects.exclude(doi_url="")
        self.assertEqual(linked.count(), 100)  # DOI 88 + 특허 12 (docs/DATA.md 7절)
        body = self.client.get(reverse("publications")).content.decode()
        self.assertEqual(body.count("DOI ↗"), 88)
        self.assertEqual(body.count("LINK ↗"), 12)
        self.assertIn(f'href="{linked.first().doi_url}"', body)

    def test_unverified_patent_number_is_not_linked(self):
        # 5번 특허의 등록번호는 다른 사람의 특허를 가리킨다 — 링크를 걸면 안 된다
        self.assertEqual(Publication.objects.get(kind="patent", order=5).doi_url, "")

    def test_admin_can_list_papers_without_links(self):
        self.client.force_login(User.objects.create_superuser("admin", "", "pw"))
        body = self.client.get("/admin/lab/publication/", {"link": "no", "all": ""}).content.decode()
        self.assertEqual(body.count('class="action-select"'), 19)
        self.assertIn('-doi_url"', body)  # 목록에서 바로 붙여넣을 수 있는 입력칸


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SyncPublicationsTest(TestCase):
    """운영 서버 반영용 sync_publications — 관리자가 고친 것은 절대 덮어쓰지 않는다."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def _as_on_server(self):
        # 2026-10 서버 상태를 재현: 링크 없음 + 예전 교정본(Improving) + 관리자가 손댄 칸 두 개
        Publication.objects.update(doi_url="")
        p = Publication.objects.get(text__contains="Improvnig MOT")
        p.text = p.text.replace("Improvnig MOT", "Improving MOT"); p.save()
        first, second = Publication.objects.filter(kind="intl_journal").order_by("order")[:2]
        first.doi_url = "https://example.org/admin-set"; first.save()
        second.text = "관리자가 고친 서지"; second.save()
        return first.pk, second.pk, p.pk

    def test_fills_only_empty_links_and_keeps_admin_edits(self):
        admin_link_pk, admin_text_pk, typo_pk = self._as_on_server()
        call_command("sync_publications", stdout=open("/dev/null", "w"), stderr=open("/dev/null", "w"))

        self.assertEqual(Publication.objects.get(pk=admin_link_pk).doi_url, "https://example.org/admin-set")
        self.assertEqual(Publication.objects.get(pk=admin_text_pk).text, "관리자가 고친 서지")
        self.assertIn("Improvnig MOT", Publication.objects.get(pk=typo_pk).text)
        self.assertEqual(Publication.objects.exclude(doi_url="").count(), 100)  # 99 채움 + 관리자 것 1

    def test_is_idempotent(self):
        self._as_on_server()
        call_command("sync_publications", stdout=open("/dev/null", "w"), stderr=open("/dev/null", "w"))
        before = list(Publication.objects.values_list("doi_url", "text"))
        call_command("sync_publications", stdout=open("/dev/null", "w"), stderr=open("/dev/null", "w"))
        self.assertEqual(before, list(Publication.objects.values_list("doi_url", "text")))

    def test_dry_run_changes_nothing(self):
        self._as_on_server()
        call_command("sync_publications", "--dry-run", stdout=open("/dev/null", "w"), stderr=open("/dev/null", "w"))
        self.assertEqual(Publication.objects.exclude(doi_url="").count(), 1)

    def test_data_migration_applies_the_same_sync_on_deploy(self):
        # 배포 때 migrate가 0005를 돌린다 — 서버 상태에서 링크가 채워지고 관리자 수정분은 남아야 한다
        import importlib
        from django.apps import apps

        admin_link_pk, admin_text_pk, typo_pk = self._as_on_server()
        importlib.import_module("lab.migrations.0005_sync_publication_links").forward(apps, None)
        self.assertEqual(Publication.objects.get(pk=admin_link_pk).doi_url, "https://example.org/admin-set")
        self.assertEqual(Publication.objects.get(pk=admin_text_pk).text, "관리자가 고친 서지")
        self.assertIn("Improvnig MOT", Publication.objects.get(pk=typo_pk).text)
        self.assertEqual(Publication.objects.exclude(doi_url="").count(), 100)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SiteRevisionTest(TestCase):
    """2026-11-03 수정 요청: 필터 버튼 · 소식 상세 · 서지 링크 · 사진 한 줄 · 운영 DB 보강."""

    @classmethod
    def setUpTestData(cls):
        call_command("load_notion", stdout=open("/dev/null", "w"))

    def test_year_buttons_default_to_all_and_filter(self):
        for name in ["publications", "gallery", "awards"]:
            self.assertRegex(self.client.get(reverse(name)).content.decode(), r'filter__btn is-active"[^>]*>전체<span>')
        body = self.client.get(reverse("publications"), {"year": 2024}).content.decode()
        self.assertEqual(body.count('class="cite"'), Publication.objects.filter(year=2024).count())
        self.assertNotIn('id="y2023"', body)
        # 없는 연도를 주면 빈 화면 대신 전체
        body = self.client.get(reverse("publications"), {"year": 1900}).content.decode()
        self.assertEqual(body.count('class="cite"'), Publication.objects.count())

    def test_year_button_keeps_kind_and_kind_tab_resets_year(self):
        body = self.client.get(reverse("publications"), {"type": "patent", "year": 2024}).content.decode()
        self.assertRegex(body, r'href="\?type=patent&amp;year=\d{4}"')
        self.assertRegex(body, r'href="\?type=intl_journal"')

    def test_every_news_item_opens(self):
        items = list(News.objects.filter(is_public=True))
        body = self.client.get(reverse("news")).content.decode()
        for n in items:
            self.assertIn(f'href="{reverse("news_detail", args=[n.pk])}"', body)
            self.assertEqual(self.client.get(reverse("news_detail", args=[n.pk])).status_code, 200)

    def test_citation_text_is_the_link(self):
        linked = Publication.objects.exclude(doi_url="").first()
        body = self.client.get(reverse("publications")).content.decode()
        self.assertIn(f'<a class="cite__link" href="{linked.doi_url}"', body)

    def test_photos_stack_and_lightbox_stays_in_its_own_group(self):
        body = self.client.get(reverse("awards")).content.decode()
        self.assertNotIn("photo-grid", body)
        self.assertNotIn('data-lightbox=""', body)
        groups = set(re.findall(r'data-lightbox="(\w+)"', body))
        self.assertGreater(len(groups), 1)

    def test_research_and_recruit_buttons(self):
        from .models import Research, ResearchGroup, Resource
        group = ResearchGroup.objects.first()
        body = self.client.get(reverse("research"), {"group": group.pk}).content.decode()
        self.assertEqual(body.count('class="group-head"'), 1)
        self.assertEqual(body.count('class="topic"'), Research.objects.filter(group=group, is_public=True).count())
        self.assertContains(self.client.get(reverse("resources")), 'class="notice"')
        env = Resource.objects.get(title_ko="PMI 연구환경")
        res = self.client.get(reverse("resources"), {"c": env.pk})
        self.assertNotContains(res, 'class="notice"')
        self.assertContains(res, "<h3>풍부한 연구실 비품</h3>")
        self.assertContains(res, "<li>스캐너 배치</li>")

    def test_outline_escapes_html(self):
        from .templatetags.lab import outline
        self.assertNotIn("<script>", outline("[<script>]\n- <script>x\n<script>"))

    def test_enrichment_fills_empty_only_and_is_idempotent(self):
        from django.apps import apps
        from .models import NewsImage
        from .seed_sync import sync_enrichment

        with_body = News.objects.exclude(body_en="").first()
        kept = News.objects.exclude(body_en="").exclude(pk=with_body.pk).first()
        News.objects.filter(pk=with_body.pk).update(body_en="")
        News.objects.filter(pk=kept.pk).update(body_en="관리자가 고친 본문")
        pub = Publication.objects.exclude(pdf="").first()
        Publication.objects.filter(pk=pub.pk).update(pdf="")
        NewsImage.objects.all().delete()

        counts = sync_enrichment(apps.get_model)
        self.assertEqual(counts["news_bodies"], 1)
        self.assertEqual(counts["pdfs"], 1)
        self.assertEqual(counts["news_images"], 2)
        self.assertEqual(counts["missing"], 0)
        self.assertEqual(News.objects.get(pk=kept.pk).body_en, "관리자가 고친 본문")
        self.assertTrue(News.objects.get(pk=with_body.pk).body_en)
        self.assertFalse(sync_enrichment(apps.get_model))
