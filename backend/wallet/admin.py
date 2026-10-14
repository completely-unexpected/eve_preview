from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from .models import Wallet,MoneyRequest,PointGrant,PointConversion,WalletEntry
from .services import decide,grant_points,reply_deposit_account

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display=["member","available","reserved","points"]
    search_fields=["member__username","member__nickname"]
    readonly_fields=["member","available","reserved","points"]
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False
    def has_change_permission(self,request,obj=None):return False

@admin.register(MoneyRequest)
class MoneyRequestAdmin(admin.ModelAdmin):
    def get_model_perms(self, request): return {}
    list_display=["member","kind","amount","bonus_name","bonus_amount","bonus_destination","status","created_at","processed_at","processed_by"]
    list_filter=["kind","status"]
    search_fields=["member__username","member__nickname"]
    readonly_fields=["member","kind","amount","status","created_at","processed_at","processed_by","bonus_option","bonus_name","bonus_percent","bonus_amount","bonus_destination","rolling_snapshot"]
    actions=["approve_selected","reject_selected"]
    def has_add_permission(self,request):return False
    def has_delete_permission(self,request,obj=None):return False
    def _process(self,request,queryset,approve):
        count=0
        for item in queryset:
            try:decide(item.pk,request.user,approve)
            except ValidationError as exc:self.message_user(request,f"신청 {item.pk}: {exc.messages[0]}",messages.WARNING)
            else:count+=1
        self.message_user(request,f"{count}건 처리했습니다.")
    @admin.action(description="선택한 신청 승인")
    def approve_selected(self,request,queryset):self._process(request,queryset,True)
    @admin.action(description="선택한 신청 거절")
    def reject_selected(self,request,queryset):self._process(request,queryset,False)

@admin.register(PointGrant)
class PointGrantAdmin(admin.ModelAdmin):
    list_display=["member","amount","reason","granted_by","created_at"]
    fields=["member","amount","reason"]
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False
    def save_model(self,request,obj,form,change):
        grant = grant_points(obj.member, obj.amount, obj.reason, request.user)
        obj.pk = grant.pk
        obj._state.adding = False

@admin.register(PointConversion)
class PointConversionAdmin(admin.ModelAdmin):
    list_display=["member","points","created_at"]
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False

@admin.register(WalletEntry)
class WalletEntryAdmin(admin.ModelAdmin):
    list_display=["wallet","kind","available_delta","reserved_delta","points_delta","reference","created_at"]
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False


from .models import DepositBonus, DepositAccount, DepositAccountRequest


@admin.register(DepositBonus)
class DepositBonusAdmin(admin.ModelAdmin):
    list_display = ["name", "bonus_percent", "destination", "is_active", "sort_order"]
    list_filter = ["is_active", "destination"]
    list_editable = ["is_active", "sort_order"]
    fieldsets = [
        ("입금 보너스", {"fields": ["name", "description", "bonus_percent", "destination", "is_active", "sort_order"]}),
        ("롤링 조건", {
            "fields": ["sports_single", "sports_double", "sports_multi", "minigame", "casino"],
            "description": "퍼센트를 입력하세요. 빈칸은 이용불가로 표시됩니다. 변경한 설정은 새 입금 신청부터 적용됩니다. 실제 게임 이용량에 따른 롤링 충족 계산은 게임 API 연결 후 적용됩니다.",
        }),
    ]


@admin.register(DepositAccount)
class DepositAccountAdmin(admin.ModelAdmin):
    list_display = ["bank_name", "account_holder", "is_active", "updated_at"]
    fields = ["bank_name", "account_number", "account_holder", "instructions", "is_active"]


@admin.register(DepositAccountRequest)
class DepositAccountRequestAdmin(admin.ModelAdmin):
    list_display = ["member", "status", "account", "created_at", "responded_at"]
    list_filter = ["status"]
    search_fields = ["member__username", "member__nickname"]
    fields = ["member", "status", "account", "created_at", "responded_at", "responded_by", "account_snapshot"]
    readonly_fields = ["member", "status", "created_at", "responded_at", "responded_by", "account_snapshot"]

    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or obj.status == "pending")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "account":
            kwargs["queryset"] = DepositAccount.objects.filter(is_active=True)
            kwargs["required"] = True
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        updated = reply_deposit_account(obj.pk, obj.account_id, request.user)
        obj.account_snapshot = updated.account_snapshot
        obj.status = updated.status
        obj.responded_at = updated.responded_at
        obj.responded_by = updated.responded_by


from .models import DepositRequest, WithdrawalRequest


class RequestKindAdmin(MoneyRequestAdmin):
    def get_model_perms(self, request): return admin.ModelAdmin.get_model_perms(self, request)
    def get_queryset(self, request): return super().get_queryset(request).filter(kind=self.request_kind)
    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("wallet.view_moneyrequest") or request.user.has_perm("wallet.change_moneyrequest")
    def has_change_permission(self, request, obj=None): return request.user.has_perm("wallet.change_moneyrequest")


@admin.register(DepositRequest)
class DepositRequestAdmin(RequestKindAdmin):
    request_kind = "deposit"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(RequestKindAdmin):
    request_kind = "withdraw"
