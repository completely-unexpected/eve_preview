from django.contrib import admin
from .models import Notice

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ["title", "is_published", "is_pinned", "created_at", "updated_at"]
    list_filter = ["is_published", "is_pinned"]
    search_fields = ["title", "body"]
    readonly_fields = ["created_at", "updated_at"]
