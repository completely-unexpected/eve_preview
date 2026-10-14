from django.contrib import admin
from .models import Game
@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_published", "sort_order"]
    list_filter = ["category", "is_published"]
    search_fields = ["name", "english_name", "slug"]
    def get_readonly_fields(self, request, obj=None):
        return ["slug"] if obj else []
