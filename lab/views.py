"""공개 페이지.

화면 구성은 시안 `03_작업메모/PMI Lab 1a v2.html`(1a 아카이브 에디토리얼)을 따른다.
템플릿·CSS만 시안에서 가져왔고 데이터 규칙은 docs/DATA.md 그대로다.
"""
from itertools import groupby

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from .models import (
    Award, GalleryEvent, Member, News, Project, Publication, Research, ResearchGroup,
    Resource, SiteSetting,
)


def site_context(request):
    return {"site": SiteSetting.load()}


def by_year(items):
    """연도 내림차순으로 묶는다. [(연도, [항목...]), ...] — 시안의 .year-block 단위."""
    items = sorted(items, key=lambda o: (o.year or 0), reverse=True)
    return [(year, list(group)) for year, group in groupby(items, key=lambda o: o.year)]


def numbered(items, total):
    """시안 규칙: 번호는 종류 안에서 역순. seed의 order(=노션 순번)는 최신이 1번이다."""
    for obj in items:
        obj.num = total - obj.order + 1
    return items


def home(request):
    return render(request, "lab/home.html", {
        "professor": Member.objects.filter(is_public=True, role=Member.Role.PROFESSOR).first(),
        "groups": ResearchGroup.objects.filter(is_public=True),
        "news": News.objects.filter(is_public=True)[:4],
    })


def members(request):
    qs = Member.objects.filter(is_public=True)
    current = list(qs.filter(is_current=True))
    roles = [
        (Member.Role.PHD, "박사과정", "Ph.D."),
        (Member.Role.MS, "석사과정", "M.S."),
        (Member.Role.UNDERGRAD, "학부연구생", "Undergraduate"),
        (Member.Role.RESEARCHER, "연구원", "Researcher"),
        (Member.Role.OTHER, "기타", "Member"),
    ]
    groups = [(label, short, [m for m in current if m.role == value]) for value, label, short in roles]
    return render(request, "lab/members.html", {
        "professor": next((m for m in current if m.role == Member.Role.PROFESSOR), None),
        "groups": [g for g in groups if g[2]],
        "current_count": len(current),
        "alumni": qs.filter(is_current=False),
    })


def publications(request):
    qs = Publication.objects.filter(is_public=True)
    counts = {row["kind"]: row["n"] for row in qs.values("kind").annotate(n=Count("id"))}
    tabs = [("all", "전체", sum(counts.values()))]
    tabs += [(value, label, counts.get(value, 0)) for value, label in Publication.Kind.choices if counts.get(value)]

    kind = request.GET.get("type", "all")
    if kind not in dict((t[0], t) for t in tabs):
        kind = "all"
    if kind != "all":
        qs = qs.filter(kind=kind)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(text__icontains=q)

    items = list(qs)
    for kind_value in {o.kind for o in items}:
        numbered([o for o in items if o.kind == kind_value], counts.get(kind_value, 0))

    return render(request, "lab/publications.html", {
        "tabs": tabs, "active": kind, "q": q,
        "total": len(items), "years": by_year(items), "show_kind": kind == "all",
    })


def projects(request):
    qs = Project.objects.filter(is_public=True)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(text__icontains=q)
    items = list(qs)
    numbered(items, Project.objects.filter(is_public=True).count())
    return render(request, "lab/projects.html", {"years": by_year(items), "total": len(items), "q": q})


def research(request):
    return render(request, "lab/research.html", {
        "groups": ResearchGroup.objects.filter(is_public=True).prefetch_related("items__media"),
    })


def gallery(request):
    events = list(GalleryEvent.objects.filter(is_public=True).prefetch_related("images"))
    groups = [(d.year if (d := ev.date) else None, ev) for ev in events]
    years = [(year, [ev for _, ev in group])
             for year, group in groupby(groups, key=lambda pair: pair[0])]
    return render(request, "lab/gallery.html", {"years": years, "total": len(events)})


def gallery_detail(request, pk):
    events = list(GalleryEvent.objects.filter(is_public=True))
    item = get_object_or_404(GalleryEvent, pk=pk, is_public=True)
    i = next(n for n, ev in enumerate(events) if ev.pk == item.pk)
    return render(request, "lab/gallery_detail.html", {
        "item": item,
        "images": item.images.all(),
        "prev": events[i - 1] if i else None,
        "next": events[i + 1] if i + 1 < len(events) else None,
    })


def news(request):
    qs = News.objects.filter(is_public=True)
    counts = {row["tag"]: row["n"] for row in qs.values("tag").annotate(n=Count("id"))}
    tabs = [("all", "전체", sum(counts.values()))]
    tabs += [(value, label, counts.get(value, 0)) for value, label in News.Tag.choices if counts.get(value)]

    tag = request.GET.get("tag", "all")
    if tag != "all" and tag in counts:
        qs = qs.filter(tag=tag)
    else:
        tag = "all"
    return render(request, "lab/news.html", {
        "items": qs.prefetch_related("images"), "tabs": tabs, "active": tag,
    })


def news_detail(request, pk):
    item = get_object_or_404(News, pk=pk, is_public=True)
    if not (item.body_ko or item.body_en or item.images.exists()):
        # 본문도 사진도 없으면 목록에서 링크하지 않는다 (24건 중 12건만 본문 있음)
        from django.http import Http404
        raise Http404
    return render(request, "lab/news_detail.html", {"item": item, "images": item.images.all()})


def awards(request):
    return render(request, "lab/awards.html", {
        "items": Award.objects.filter(is_public=True).prefetch_related("images"),
    })


def resources(request):
    return render(request, "lab/resources.html", {
        "items": Resource.objects.filter(is_public=True).prefetch_related("media"),
        "recruit": SiteSetting.load(),
    })
