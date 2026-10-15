from django.contrib import admin
from .models import Game
@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    change_list_template = 'admin/catalog/game/change_list.html'

    def get_urls(self):
        from django.urls import path
        from .odds_admin import manage
        from .reset_matches import reset_view
        return [path('odds/reset/',self.admin_site.admin_view(lambda request:reset_view(self,request)),name='catalog_game_reset_matches'),path('odds/', self.admin_site.admin_view(lambda request: manage(self, request)), name='catalog_game_odds')] + super().get_urls()

    list_display = ["name", "category", "is_published", "sort_order"]
    list_filter = ["category", "is_published"]
    search_fields = ["name", "english_name", "slug"]
    def get_readonly_fields(self, request, obj=None):
        return ["slug"] if obj else []
