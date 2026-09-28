"""공개 페이지. 뷰·URL은 1단계에서 확정하고 2단계(시안 적용)에서는 템플릿·CSS만 바꾼다."""
from django.shortcuts import get_object_or_404, render

from .models import Award, GalleryEvent, Member, News, Project, Publication, Research, Resource, SiteSetting


def site_context(request):
    return {"site": SiteSetting.load()}


def home(request):
    members = Member.objects.filter(is_public=True, is_current=True)
    return render(request, "lab/home.html", {
        "professor": members.filter(role=Member.Role.PROFESSOR).first(),
        "news": News.objects.filter(is_public=True)[:5],
        "awards": Award.objects.filter(is_public=True).prefetch_related("images")[:3],
    })


def members(request):
    qs = Member.objects.filter(is_public=True)
    current = qs.filter(is_current=True)
    groups = [(label, [m for m in current if m.role == value]) for value, label in Member.Role.choices]
    return render(request, "lab/members.html", {
        "groups": [(label, ms) for label, ms in groups if ms],
        "alumni": qs.filter(is_current=False),
    })


def publications(request):
    qs = Publication.objects.filter(is_public=True)
    groups = [(label, [p for p in qs if p.kind == value]) for value, label in Publication.Kind.choices]
    return render(request, "lab/publications.html", {"groups": [(l, ps) for l, ps in groups if ps]})


def research(request):
    return render(request, "lab/research.html", {
        "items": Research.objects.filter(is_public=True).prefetch_related("media"),
    })


def projects(request):
    return render(request, "lab/projects.html", {"items": Project.objects.filter(is_public=True)})


def gallery(request):
    return render(request, "lab/gallery.html", {
        "items": GalleryEvent.objects.filter(is_public=True).prefetch_related("images"),
    })


def gallery_detail(request, pk):
    return render(request, "lab/gallery_detail.html", {
        "item": get_object_or_404(GalleryEvent, pk=pk, is_public=True),
    })


def news(request):
    return render(request, "lab/news.html", {"items": News.objects.filter(is_public=True)})


def awards(request):
    return render(request, "lab/awards.html", {
        "items": Award.objects.filter(is_public=True).prefetch_related("images"),
    })


def resources(request):
    return render(request, "lab/resources.html", {
        "items": Resource.objects.filter(is_public=True).prefetch_related("media"),
    })
