from django.contrib import admin

from .models import GalleryPhoto, GalleryTag


@admin.register(GalleryTag)
class GalleryTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)


@admin.register(GalleryPhoto)
class GalleryPhotoAdmin(admin.ModelAdmin):
    list_display = ("title", "created_at", "active", "uploaded_by", "job")
    list_filter = ("active", "tags")
    search_fields = ("title", "description")
    filter_horizontal = ("tags",)
