"""공개 페이지.

화면 구성은 시안 `03_작업메모/PMI Lab 1a v2.html`(1a 아카이브 에디토리얼)을 따른다.
템플릿·CSS만 시안에서 가져왔고 데이터 규칙은 docs/DATA.md 그대로다.
"""
from collections import Counter
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


def year_filter(request, items, year_of):
    """연도 버튼. (버튼 [(값, 라벨, 건수)...], 고른 값, 고른 항목들). 기본은 전체, 없는 연도를 주면 전체."""
    counts = Counter(year_of(o) for o in items)
    years = sorted(counts, key=lambda y: y or 0, reverse=True)
    buttons = [("", "전체", len(items))] + [(str(y), y or "연도 미상", counts[y]) for y in years]
    active = request.GET.get("year", "")
    if active not in [b[0] for b in buttons]:
        active = ""
    return buttons, active, [o for o in items if not active or str(year_of(o)) == active]


def event_year(obj):
    return obj.date.year if obj.date else None


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
    public = Publication.objects.filter(is_public=True)

    q = request.GET.get("q", "").strip()
    found = public.filter(text__icontains=q) if q else public

    # 탭 건수는 검색 결과 기준이어야 한다. 전체 건수를 보여주면 눌렀을 때 그만큼 안 나온다
    counts = {row["kind"]: row["n"] for row in found.values("kind").annotate(n=Count("id"))}
    tabs = [("all", "전체", sum(counts.values()))]
    tabs += [(value, label, counts.get(value, 0)) for value, label in Publication.Kind.choices]

    kind = request.GET.get("type", "all")
    if kind not in dict(Publication.Kind.choices):
        kind = "all"

    buttons, year, items = year_filter(request, list(found if kind == "all" else found.filter(kind=kind)), lambda p: p.year)
    return render(request, "lab/publications.html", {
        "tabs": tabs, "active": kind, "q": q, "buttons": buttons, "year": year,
        "total": len(items), "years": by_year(items), "show_kind": kind == "all",
    })


def projects(request):
    qs = Project.objects.filter(is_public=True)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(text__icontains=q)
    items = list(qs)
    return render(request, "lab/projects.html", {"years": by_year(items), "total": len(items), "q": q})


def research(request):
    groups = list(ResearchGroup.objects.filter(is_public=True).prefetch_related("items__media"))
    active = next((g for g in groups if str(g.pk) == request.GET.get("group")), None)
    return render(request, "lab/research.html", {
        "groups": groups, "active": active, "shown": [active] if active else groups,
    })


def gallery(request):
    events = list(GalleryEvent.objects.filter(is_public=True).prefetch_related("images"))
    buttons, year, shown = year_filter(request, events, event_year)
    years = [(y, list(group)) for y, group in groupby(shown, key=event_year)]
    return render(request, "lab/gallery.html", {
        "years": years, "total": len(shown), "buttons": buttons, "year": year,
    })


def gallery_detail(request, pk):
    events = list(GalleryEvent.objects.filter(is_public=True))
    item = get_object_or_404(GalleryEvent, pk=pk, is_public=True)
    i = next(n for n, ev in enumerate(events) if ev.pk == item.pk)
    # 목록이 최신순이라 배열의 다음 칸이 더 과거다. "이전 행사" = 더 과거여야 말이 된다
    return render(request, "lab/gallery_detail.html", {
        "item": item,
        "images": item.images.all(),
        "prev": events[i + 1] if i + 1 < len(events) else None,
        "next": events[i - 1] if i else None,
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
    return render(request, "lab/news_detail.html", {"item": item, "images": item.images.all()})


def awards(request):
    buttons, year, items = year_filter(
        request, list(Award.objects.filter(is_public=True).prefetch_related("images")), event_year)
    return render(request, "lab/awards.html", {"items": items, "buttons": buttons, "year": year})


def resources(request):
    items = list(Resource.objects.filter(is_public=True).prefetch_related("media"))
    return render(request, "lab/resources.html", {
        "items": items,
        "active": next((r for r in items if str(r.pk) == request.GET.get("c")), None),  # 없으면 모집 안내
    })
