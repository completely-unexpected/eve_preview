from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("회원 정보", {"fields": ("nickname", "account_status")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("회원 정보", {"fields": ("nickname", "account_status")}),
    )
    list_display = ("username", "nickname", "account_status", "is_active", "is_staff", "date_joined")
    list_filter = ("account_status", "is_staff", "is_superuser")
    search_fields = ("username", "nickname", "email")
    readonly_fields = ("is_active",)
    actions = ("approve_members", "suspend_members", "restore_members")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj and (obj.is_staff or obj.is_superuser):
            return (*fields, "account_status")
        return fields

    def _change_status(self, request, queryset, previous, target, description):
        if not self.has_change_permission(request):
            raise PermissionDenied
        changed = 0
        with transaction.atomic():
            members = queryset.select_for_update().filter(
                is_staff=False, is_superuser=False, account_status=previous,
            )
            for member in members:
                member.account_status = target
                member.save(update_fields=("account_status",))
                self.log_change(request, member, description)
                changed += 1
        self.message_user(
            request, f"{description}: {changed}명 처리했습니다. 관리자 계정과 다른 상태의 회원은 제외됩니다.",
            messages.SUCCESS if changed else messages.WARNING,
        )

    @admin.action(description="선택한 회원 가입 승인", permissions=("change",))
    def approve_members(self, request, queryset):
        self._change_status(request, queryset, User.Status.PENDING, User.Status.APPROVED, "가입 승인")

    @admin.action(description="선택한 회원 이용 정지", permissions=("change",))
    def suspend_members(self, request, queryset):
        self._change_status(request, queryset, User.Status.APPROVED, User.Status.SUSPENDED, "이용 정지")

    @admin.action(description="선택한 정지 회원 이용 재개", permissions=("change",))
    def restore_members(self, request, queryset):
        self._change_status(request, queryset, User.Status.SUSPENDED, User.Status.APPROVED, "이용 재개")
