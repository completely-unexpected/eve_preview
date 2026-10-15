from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import PermissionDenied
from django.db import transaction

from .models import User, MemberLevel, PartnerAccount
from django.utils.html import format_html,format_html_join
from django.urls import reverse
from .member_columns import MemberColumns,member_metrics


@admin.register(User)
class CustomUserAdmin(MemberColumns,UserAdmin):
    change_form_template='admin/accounts/user/change_form.html'
    fieldsets = (
        ('개인정보',{'fields':('username','nickname','legal_name','phone_number','wallet_number','member_ip','member_location','member_financial_summary','admin_notes')}),
        ('계정·소속 정보',{'fields':('password','account_status','level','wallet_name','partner','referrer')}),
        *UserAdmin.fieldsets[2:],
    )
    fieldsets += (("회원별 예외 이용한도", {"fields": ("single_min", "single_max", "single_payout", "multi_min", "multi_max", "multi_payout"), "description": "빈칸은 레벨별 한도를 사용합니다. 회원 화면에서는 관리자 설정을 조회합니다."}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("회원 정보", {"fields": ("nickname", "account_status", "level", "wallet_name", "referrer")}),
    )
    add_fieldsets += (("추천인 / 하위협력사", {"fields": ("partner",)}),)
    list_display = MemberColumns.member_columns
    autocomplete_fields=('referrer',)
    def get_queryset(self,request): return member_metrics(super().get_queryset(request))
    list_select_related = ("level", "partner")
    list_filter = ("account_status", "level", "partner", "is_staff", "is_superuser")
    search_fields = ("username", "nickname", "email", "partner__username", "partner__name")
    readonly_fields = ("is_active","member_ip","member_location","member_financial_summary")

    @admin.display(description='회원 금액·이용현황')
    def member_financial_summary(self,obj):
        if not obj: return '회원 저장 후 표시됩니다.'
        labels=('보유머니','보유포인트','누적충전 / 누적환전','당일충전','당일환전','당일배팅','수익금','추천인')
        values=(self.member_money(obj),self.member_points(obj),self.member_lifetime(obj),self.member_today_deposit(obj),self.member_today_withdraw(obj),self.member_bets(obj),self.member_profit(obj),self.member_referrer(obj))
        return format_html('<div class="member-financial-scroll"><table class="member-financial-table"><thead><tr>{}</tr></thead><tbody><tr>{}</tr></tbody></table></div>',format_html_join('','<th scope="col">{}</th>',((label,) for label in labels)),format_html_join('','<td>{}</td>',((value,) for value in values)))

    def current_presence(self,obj):
        if not obj: return None
        if not hasattr(obj,'_detail_presence'):
            from activity.models import PagePresence
            obj._detail_presence=PagePresence.objects.filter(actor=obj.username,actor_kind__in=['member','admin']).order_by('-last_seen').first()
        return obj._detail_presence

    @admin.display(description='접속 IP')
    def member_ip(self,obj):
        presence=self.current_presence(obj)
        return presence.last_ip if presence and presence.last_ip else '아직 확인되지 않음'

    @admin.display(description='현재 이용 위치')
    def member_location(self,obj):
        from activity.pages import page_name
        from django.utils import timezone
        from datetime import timedelta
        presence=self.current_presence(obj)
        if not presence: return '확인된 이용 기록 없음'
        return page_name(presence.route)+(' (최근 위치 · 현재 활동 확인 안 됨)' if presence.last_seen<timezone.now()-timedelta(seconds=90) else '')
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


from django import forms
from django.contrib.auth.password_validation import validate_password


class PartnerAccountForm(forms.ModelForm):
    new_password = forms.CharField(label="비밀번호", required=False, strip=False, widget=forms.PasswordInput(render_value=False), help_text="새 계정은 필수입니다. 수정 시 비워두면 기존 비밀번호가 유지됩니다.")
    confirm_password = forms.CharField(label="비밀번호 확인", required=False, strip=False, widget=forms.PasswordInput(render_value=False))

    class Meta:
        model = PartnerAccount
        fields = ("username", "name", "is_active")

    def clean(self):
        data = super().clean()
        password = data.get("new_password")
        if not self.instance.pk and not password:
            self.add_error("new_password", "비밀번호를 입력해 주세요.")
        if password != data.get("confirm_password"):
            self.add_error("confirm_password", "비밀번호가 일치하지 않습니다.")
        if password:
            self.instance.username = data.get("username", "")
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as exc:
                self.add_error("new_password", exc)
        return data

    def save(self, commit=True):
        account = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            account.set_password(self.cleaned_data["new_password"])
        if commit:
            account.save()
        return account


@admin.register(PartnerAccount)
class PartnerAccountAdmin(admin.ModelAdmin):
    form = PartnerAccountForm
    list_display = ("username", "name", "is_active", "referral_code", "member_link", "last_login")
    list_filter = ("is_active",)
    search_fields = ("username", "name", "referral_code")
    readonly_fields = ("referral_code", "member_link", "portal_link", "created_at", "last_login")
    fields = ("username", "name", "is_active", "new_password", "confirm_password", "referral_code", "member_link", "portal_link", "created_at", "last_login")

    @admin.display(description="연결 회원")
    def member_link(self, obj):
        if not obj.pk:
            return "저장 후 확인할 수 있습니다."
        return format_html('<a href="{}?partner__id__exact={}">{}명 보기</a>', reverse("admin:accounts_user_changelist"), obj.pk, obj.members.count())

    @admin.display(description="협력사 전용 로그인")
    def portal_link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">전용 관리자창 열기</a>', reverse("partner_admin_login"))

    def has_delete_permission(self, request, obj=None):
        return False
