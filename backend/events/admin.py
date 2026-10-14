from django.contrib import admin
from .models import Event
@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["title", "is_published", "sort_order"]
    list_filter = ["is_published"]
    search_fields = ["title", "summary", "body"]
