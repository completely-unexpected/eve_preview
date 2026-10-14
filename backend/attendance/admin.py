from django.contrib import admin
from .models import Attendance, AttendanceReward, AttendanceSettings


@admin.register(AttendanceSettings)
class AttendanceSettingsAdmin(admin.ModelAdmin):
    list_display = ["is_active", "minimum_deposit", "daily_points", "streak_days", "streak_points", "monthly_days", "monthly_points"]
    fields = ["is_active", "minimum_deposit", "daily_points", "streak_days", "streak_points", "monthly_days", "monthly_points"]

    def has_add_permission(self, request):
        return not AttendanceSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyAttendanceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(Attendance)
class AttendanceAdmin(ReadOnlyAttendanceAdmin):
    list_display = ["member", "date", "deposit_amount", "streak", "awarded_points"]
    list_filter = ["date"]
    search_fields = ["member__username", "member__nickname"]
    readonly_fields = ["member", "date", "deposit_amount", "streak", "awarded_points", "conditions", "created_at"]


@admin.register(AttendanceReward)
class AttendanceRewardAdmin(ReadOnlyAttendanceAdmin):
    list_display = ["member", "month", "kind", "points", "created_at"]
    list_filter = ["month", "kind"]
    search_fields = ["member__username", "member__nickname"]
    readonly_fields = ["member", "attendance", "month", "kind", "points", "created_at"]
