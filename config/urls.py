from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path

from lab import views

urlpatterns = [
    path("", views.home, name="home"),
    path("members/", views.members, name="members"),
    path("publications/", views.publications, name="publications"),
    path("research/", views.research, name="research"),
    path("projects/", views.projects, name="projects"),
    path("gallery/", views.gallery, name="gallery"),
    path("gallery/<int:pk>/", views.gallery_detail, name="gallery_detail"),
    path("news/", views.news, name="news"),
    path("news/<int:pk>/", views.news_detail, name="news_detail"),
    path("awards/", views.awards, name="awards"),
    path("resources/", views.resources, name="resources"),
    path("admin/", admin.site.urls),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # DEBUG일 때만 동작. 서버는 Caddy가 서빙
