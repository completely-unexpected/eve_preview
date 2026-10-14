from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import User, MemberLevel


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("회원 정보", {"fields": ("nickname", "account_status", "level")}),
    )
    fieldsets += (("회원별 예외 이용한도", {"fields": ("single_min", "single_max", "single_payout", "multi_min", "multi_max", "multi_payout"), "description": "빈칸은 레벨별 한도를 사용합니다. 회원 화면에서는 관리자 설정을 조회합니다."}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("회원 정보", {"fields": ("nickname", "account_status", "level")}),
    )
    list_display = ("username", "nickname", "account_status", "level", "is_active", "is_staff", "date_joined")
    list_filter = ("account_status", "level", "is_staff", "is_superuser")
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


@admin.register(MemberLevel)
class MemberLevelAdmin(admin.ModelAdmin):
    list_display = ["number", "name", "single_min", "single_max", "single_payout", "multi_min", "multi_max", "multi_payout"]
    fields = ["number", "name", "single_min", "single_max", "single_payout", "multi_min", "multi_max", "multi_payout"]

    def get_readonly_fields(self, request, obj=None):
        return ("number",) if obj else ()

    def has_delete_permission(self, request, obj=None):
        if obj and obj.number == 1:
            return False
        return super().has_delete_permission(request, obj)
