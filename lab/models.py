"""모델 정의. 명세는 docs/DATA.md 3절.

화면에 보이는 텍스트는 _ko/_en 쌍이고, 표시할 때는 템플릿 필터 `tr`로 ko or en.
"""
import uuid
from pathlib import Path

from django.db import models
from django.urls import reverse


def ascii_upload(folder):
    """업로드 파일명을 무작위 ASCII로 바꾼다. 한글 파일명은 macOS(NFD)/Linux(NFC)에서 깨진다 (CLAUDE.md 규칙 1)."""

    def upload_to(instance, filename):
        return f"{folder}/{uuid.uuid4().hex[:16]}{Path(filename).suffix.lower()}"

    upload_to.__qualname__ = upload_to.__name__ = f"upload_{folder}"
    return upload_to


# 마이그레이션이 참조할 수 있도록 모듈 수준에 둔다
upload_site = ascii_upload("site")
upload_members = ascii_upload("members")
upload_publications = ascii_upload("publications")
upload_news = ascii_upload("news")
upload_gallery = ascii_upload("gallery")
upload_research = ascii_upload("research")
upload_resources = ascii_upload("resources")
upload_awards = ascii_upload("awards")


class Listed(models.Model):
    order = models.IntegerField("순서", default=0, help_text="작을수록 위")
    is_public = models.BooleanField("공개", default=True)

    class Meta:
        abstract = True


class MediaKind(models.TextChoices):
    IMAGE = "image", "이미지"
    VIDEO = "video", "영상"


class SiteSetting(models.Model):
    lab_name_ko = models.CharField("연구실명(국문)", max_length=200, blank=True)
    lab_name_en = models.CharField("연구실명(영문)", max_length=200, blank=True)
    lab_short = models.CharField("약칭", max_length=100, blank=True)
    email = models.EmailField("대표 이메일", blank=True)
    address_ko = models.CharField("주소(국문)", max_length=300, blank=True)
    address_en = models.CharField("주소(영문)", max_length=300, blank=True)
    recruit_notice_ko = models.TextField("모집 공지(국문)", blank=True)
    recruit_notice_en = models.TextField("모집 공지(영문)", blank=True)
    home_image = models.ImageField("홈 대표 사진", upload_to=upload_site, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = "사이트 설정"

    def __str__(self):
        return "사이트 설정"

    @classmethod
    def load(cls):
        return cls.objects.first() or cls()


class Member(Listed):
    class Role(models.TextChoices):
        PROFESSOR = "professor", "교수"
        PHD = "phd", "박사과정"
        MS = "ms", "석사과정"
        UNDERGRAD = "undergrad", "학부연구생"
        RESEARCHER = "researcher", "연구원"
        OTHER = "other", "기타"

    name_ko = models.CharField("이름(국문)", max_length=100, blank=True)
    name_en = models.CharField("이름(영문)", max_length=100, blank=True)
    role = models.CharField("구분", max_length=20, choices=Role.choices, default=Role.OTHER)
    status_text = models.CharField("직함 원문", max_length=200, blank=True, help_text="노션 Status 원문")
    email = models.EmailField("이메일", blank=True)
    research_interests = models.CharField("연구 분야", max_length=300, blank=True)
    photo = models.ImageField("사진", upload_to=upload_members, blank=True)
    cv = models.FileField("CV", upload_to=upload_members, blank=True)
    bio_ko = models.TextField("소개(국문)", blank=True)
    bio_en = models.TextField("소개(영문)", blank=True)
    is_current = models.BooleanField("현재 멤버", default=True)
    career_after = models.CharField("진로", max_length=200, blank=True)
    import_note = models.TextField("적재 메모", blank=True, help_text="노션 출처·표기 변형·이메일 전체. 손실 방지용")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "멤버"

    def __str__(self):
        return self.name_ko or self.name_en


class Publication(Listed):
    class Kind(models.TextChoices):
        INTL_JOURNAL = "intl_journal", "국제 저널"
        INTL_CONFERENCE = "intl_conference", "국제 학회"
        DOM_JOURNAL = "dom_journal", "국내 저널"
        DOM_CONFERENCE = "dom_conference", "국내 학회"
        PATENT = "patent", "특허"

    kind = models.CharField("종류", max_length=20, choices=Kind.choices)
    text = models.TextField("서지 정보", help_text="화면에 표시되는 문장")
    raw = models.TextField("원문", blank=True, help_text="노션 마크다운 원문. 수정하지 말 것")
    year = models.PositiveSmallIntegerField("연도", null=True, blank=True)
    pdf = models.FileField("PDF", upload_to=upload_publications, blank=True)
    doi_url = models.URLField("DOI/링크", blank=True)

    class Meta:
        ordering = ["kind", "order", "id"]
        verbose_name = verbose_name_plural = "논문·특허"

    def __str__(self):
        return self.text[:80]


class News(models.Model):
    class Tag(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        RECRUIT = "recruit", "Recruit"
        PATENT = "patent", "Patent"
        NEWS = "news", "News"

    title_ko = models.CharField("제목(국문)", max_length=300, blank=True)
    title_en = models.CharField("제목(영문)", max_length=300, blank=True)
    date = models.DateField("날짜", null=True, blank=True)
    tag = models.CharField("분류", max_length=20, choices=Tag.choices, default=Tag.NEWS)
    body_ko = models.TextField("본문(국문)", blank=True)
    body_en = models.TextField("본문(영문)", blank=True)
    link = models.URLField("링크", blank=True)
    is_public = models.BooleanField("공개", default=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = verbose_name_plural = "소식"

    def __str__(self):
        return self.title_ko or self.title_en

    def get_absolute_url(self):
        """관리자의 "사이트에서 보기"와 sitemap.xml이 쓴다."""
        return reverse("news_detail", args=[self.pk])


class NewsImage(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("사진", upload_to=upload_news)
    order = models.IntegerField("순서", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "사진"


class GalleryEvent(Listed):
    title_ko = models.CharField("제목(국문)", max_length=300, blank=True)
    title_en = models.CharField("제목(영문)", max_length=300, blank=True)
    date = models.DateField("날짜", null=True, blank=True)
    date_end = models.DateField("종료일", null=True, blank=True)
    location = models.CharField("장소", max_length=200, blank=True)
    description_ko = models.TextField("설명(국문)", blank=True)
    description_en = models.TextField("설명(영문)", blank=True)

    class Meta:
        ordering = ["-date", "order", "-id"]
        verbose_name = verbose_name_plural = "갤러리"

    def __str__(self):
        return self.title_ko or self.title_en

    def get_absolute_url(self):
        """관리자의 "사이트에서 보기"와 sitemap.xml이 쓴다."""
        return reverse("gallery_detail", args=[self.pk])


class GalleryImage(models.Model):
    event = models.ForeignKey(GalleryEvent, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("사진", upload_to=upload_gallery)
    order = models.IntegerField("순서", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "사진"


class ResearchGroup(Listed):
    """연구 대주제. 노션 홈의 연구 분야 5분류(`site.json`의 research_groups)."""

    title_ko = models.CharField("제목(국문)", max_length=200, blank=True)
    title_en = models.CharField("제목(영문)", max_length=200, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "연구 분야"

    def __str__(self):
        return self.title_ko or self.title_en


class Research(Listed):
    group = models.ForeignKey(
        ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="items", verbose_name="연구 분야",
    )
    title_ko = models.CharField("제목(국문)", max_length=300, blank=True)
    title_en = models.CharField("제목(영문)", max_length=300, blank=True)
    subtitle = models.CharField("부제", max_length=300, blank=True)
    description_ko = models.TextField("설명(국문)", blank=True)
    description_en = models.TextField("설명(영문)", blank=True)

    class Meta:
        ordering = ["group__order", "order", "id"]
        verbose_name = verbose_name_plural = "연구"

    def __str__(self):
        return self.title_ko or self.title_en


class ResearchMedia(models.Model):
    research = models.ForeignKey(Research, on_delete=models.CASCADE, related_name="media")
    file = models.FileField("파일", upload_to=upload_research)
    kind = models.CharField("종류", max_length=10, choices=MediaKind.choices, default=MediaKind.IMAGE)
    order = models.IntegerField("순서", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "이미지·영상"


class Resource(Listed):
    title_ko = models.CharField("제목(국문)", max_length=300, blank=True)
    title_en = models.CharField("제목(영문)", max_length=300, blank=True)
    subtitle = models.CharField("부제", max_length=300, blank=True)
    body_ko = models.TextField("본문(국문)", blank=True)
    body_en = models.TextField("본문(영문)", blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "자료실"

    def __str__(self):
        return self.title_ko or self.title_en


class ResourceMedia(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name="media")
    file = models.FileField("파일", upload_to=upload_resources)
    kind = models.CharField("종류", max_length=10, choices=MediaKind.choices, default=MediaKind.IMAGE)
    order = models.IntegerField("순서", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "이미지·영상"


class Award(Listed):
    title_ko = models.CharField("제목(국문)", max_length=300, blank=True)
    title_en = models.CharField("제목(영문)", max_length=300, blank=True)
    date = models.DateField("날짜", null=True, blank=True)
    recipients = models.CharField("수상자", max_length=300, blank=True)

    class Meta:
        ordering = ["-date", "order", "-id"]
        verbose_name = verbose_name_plural = "수상"

    def __str__(self):
        return self.title_ko or self.title_en


class AwardImage(models.Model):
    award = models.ForeignKey(Award, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField("사진", upload_to=upload_awards)
    order = models.IntegerField("순서", default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "사진"


class Project(Listed):
    text = models.TextField("과제 정보", help_text="화면에 표시되는 문장")
    raw = models.TextField("원문", blank=True, help_text="노션 마크다운 원문. 수정하지 말 것")
    year = models.PositiveSmallIntegerField("연도", null=True, blank=True, help_text="정렬용. 노션 기준 종료 연도")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = verbose_name_plural = "프로젝트"

    def __str__(self):
        return self.text[:80]
