"""sitemap.xml — 대학원 지원자가 검색으로 들어오는 것이 이 사이트의 주 유입 경로다.

django.contrib.sites를 쓰지 않으므로 도메인은 요청에서 가져온다(RequestSite).
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import GalleryEvent, News

STATIC_PAGES = [
    ("home", 1.0), ("research", 0.8), ("publications", 0.8), ("projects", 0.6),
    ("members", 0.8), ("news", 0.6), ("awards", 0.5), ("gallery", 0.6), ("resources", 0.7),
]


class StaticSitemap(Sitemap):
    changefreq = "monthly"

    def items(self):
        return STATIC_PAGES

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]


class GallerySitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.4

    def items(self):
        return GalleryEvent.objects.filter(is_public=True, images__isnull=False).distinct()

    def lastmod(self, obj):
        return obj.date


class NewsSitemap(Sitemap):
    changefreq = "yearly"
    priority = 0.4

    def items(self):
        # 상세 페이지는 전부 열리지만, 제목뿐인 빈 페이지는 검색에 내보내지 않는다
        return [n for n in News.objects.filter(is_public=True).prefetch_related("images")
                if n.body_ko or n.body_en or n.images.exists()]

    def lastmod(self, obj):
        return obj.date


SITEMAPS = {"static": StaticSitemap, "gallery": GallerySitemap, "news": NewsSitemap}
