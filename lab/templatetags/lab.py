import os
import re

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.template.defaultfilters import linebreaksbr
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def tr(obj, field):
    """{{ obj|tr:"title" }} → title_ko, 없으면 title_en (CLAUDE.md 규칙 2)."""
    return getattr(obj, f"{field}_ko", "") or getattr(obj, f"{field}_en", "")


@register.filter
def email(address):
    """봇 수집 방지: HTML에 '@'와 mailto가 없다. base.html의 스크립트가 링크로 조립한다 (규칙 9)."""
    if not address or "@" not in address:
        return ""
    user, domain = address.split("@", 1)
    return format_html('<a class="email" data-u="{}" data-d="{}">{} [at] {}</a>', user, domain, user, domain)


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@register.filter
def hide_emails(text):
    """자유 텍스트(모집 공지·본문) 안의 이메일도 email 필터처럼 바꾼다. 줄바꿈은 <br>."""
    parts = EMAIL_RE.split(text or "")
    found = EMAIL_RE.findall(text or "")
    out = [linebreaksbr(parts[0])]
    for addr, rest in zip(found, parts[1:]):
        out += [email(addr), linebreaksbr(rest)]
    return mark_safe("".join(str(x) for x in out))


@register.filter(needs_autoescape=True)
def highlight(text, term, autoescape=True):
    """검색어를 <mark>로 감싼다. 시안 .cite__text mark 스타일. 이스케이프 후 감싸므로 주입 안전."""
    escaped = conditional_escape(text)
    if not term:
        return mark_safe(escaped)
    parts = re.split(f"({re.escape(conditional_escape(term))})", escaped, flags=re.I)
    return mark_safe("".join(
        f"<mark>{p}</mark>" if i % 2 else p for i, p in enumerate(parts)
    ))


@register.simple_tag
def asset(path):
    """정적 파일 주소 뒤에 수정 시각을 붙인다 (site.css?v=1791...).

    로컬 개발 서버는 파일 이름이 늘 같아서, CSS를 고쳐도 브라우저가 옛 파일을 계속 쓴다.
    운영은 ManifestStaticFilesStorage가 이름에 해시를 붙이므로 ?v= 는 붙어도 해가 없다.
    """
    found = finders.find(path)
    return f"{static(path)}?v={int(os.path.getmtime(found)) if found else 0}"
