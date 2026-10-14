from django.contrib import admin, messages
from .models import FeedSnapshot
from .collector import collect
from .services import ProviderError

@admin.register(FeedSnapshot)
class FeedSnapshotAdmin(admin.ModelAdmin):
    list_display = ["__str__", "fetched_at", "syncing", "last_error"]
    readonly_fields = ["fetched_at", "syncing", "started_at", "last_error"]
    fields = readonly_fields
    actions = ["refresh_feed"]
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    @admin.action(description="전체 경기·배당 다시 조회 (크레딧 사용)", permissions=["change"])
    def refresh_feed(self, request, queryset):
        try:
            snapshot = collect(force=True)
            self.message_user(request, f"{len(snapshot.payload.get('items', []))}개 경기 조회. 남은 크레딧: {snapshot.payload.get('remainingCredits')}")
        except ProviderError as exc:
            self.message_user(request, str(exc), messages.ERROR)
