import re

from django import template
from django.template.defaultfilters import linebreaksbr
from django.utils.html import format_html
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
