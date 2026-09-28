from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Award, AwardImage, GalleryEvent, GalleryImage, Member, News, Project, Publication,
    Research, ResearchMedia, Resource, ResourceMedia, SiteSetting,
)

admin.site.site_header = "PMI Lab 홈페이지 관리"
admin.site.site_title = "PMI Lab 관리"
admin.site.index_title = "콘텐츠 관리"


def thumb(f, is_image=True):
    if not f:
        return "-"
    if is_image:
        return format_html('<img src="{}" style="max-height:80px;max-width:120px">', f.url)
    return format_html('<a href="{}" target="_blank">열기</a>', f.url)


class ImageInline(admin.TabularInline):
    extra = 1
    fields = ["preview", "image", "order"]
    readonly_fields = ["preview"]

    @admin.display(description="미리보기")
    def preview(self, obj):
        return thumb(obj.image)


class MediaInline(admin.TabularInline):
    extra = 1
    fields = ["preview", "file", "kind", "order"]
    readonly_fields = ["preview"]

    @admin.display(description="미리보기")
    def preview(self, obj):
        return thumb(obj.file, obj.kind == "image")


class GalleryImageInline(ImageInline):
    model = GalleryImage


class AwardImageInline(ImageInline):
    model = AwardImage


class ResearchMediaInline(MediaInline):
    model = ResearchMedia


class ResourceMediaInline(MediaInline):
    model = ResourceMedia


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ["__str__", "name_en", "role", "photo_preview", "is_current", "is_public", "order"]
    list_editable = ["is_current", "is_public", "order"]
    list_filter = ["is_current", "role", "is_public"]
    search_fields = ["name_ko", "name_en", "email", "status_text", "research_interests", "career_after"]
    readonly_fields = ["photo_preview"]
    fieldsets = [
        (None, {"fields": ["name_ko", "name_en", "role", "status_text", "is_current", "career_after",
                           "email", "research_interests", "photo_preview", "photo", "bio_ko", "bio_en",
                           "order", "is_public"]}),
        ("노션 적재 메모", {"classes": ["collapse"], "fields": ["import_note"]}),
    ]

    @admin.display(description="사진")
    def photo_preview(self, obj):
        return thumb(obj.photo)


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["__str__", "kind", "year", "has_pdf", "is_public", "order"]
    list_editable = ["is_public", "order"]
    list_filter = ["kind", "year", "is_public"]
    search_fields = ["text"]

    @admin.display(description="PDF", boolean=True)
    def has_pdf(self, obj):
        return bool(obj.pdf)


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ["__str__", "date", "tag", "is_public"]
    list_editable = ["is_public"]
    list_filter = ["tag", "is_public"]
    search_fields = ["title_ko", "title_en", "body_ko", "body_en"]
    date_hierarchy = "date"


@admin.register(GalleryEvent)
class GalleryEventAdmin(admin.ModelAdmin):
    list_display = ["__str__", "date", "location", "image_count", "is_public"]
    list_editable = ["is_public"]
    list_filter = ["is_public"]
    search_fields = ["title_ko", "title_en", "location", "description_ko"]
    date_hierarchy = "date"
    inlines = [GalleryImageInline]

    @admin.display(description="사진 수")
    def image_count(self, obj):
        return obj.images.count()


@admin.register(Research)
class ResearchAdmin(admin.ModelAdmin):
    list_display = ["__str__", "subtitle", "is_public", "order"]
    list_editable = ["is_public", "order"]
    search_fields = ["title_ko", "title_en", "subtitle"]
    inlines = [ResearchMediaInline]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["__str__", "subtitle", "is_public", "order"]
    list_editable = ["is_public", "order"]
    search_fields = ["title_ko", "title_en", "subtitle"]
    inlines = [ResourceMediaInline]


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = ["__str__", "date", "recipients", "is_public"]
    list_editable = ["is_public"]
    search_fields = ["title_ko", "title_en", "recipients"]
    inlines = [AwardImageInline]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["__str__", "year", "is_public", "order"]
    list_editable = ["is_public", "order"]
    list_filter = ["is_public"]
    search_fields = ["text"]
