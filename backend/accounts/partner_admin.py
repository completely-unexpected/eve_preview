from django.contrib.auth.hashers import make_password
from django.utils.crypto import constant_time_compare
from django.middleware.csrf import rotate_token
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from .models import User, PartnerAccount
from . import throttle


def current_partner(request):
    account_id = request.session.get("partner_account_id")
    if not isinstance(account_id, int):
        return None
    account = PartnerAccount.objects.filter(pk=account_id, is_active=True).first()
    if account is None or not constant_time_compare(request.session.get("partner_auth_hash", ""), account.session_hash()):
        request.session.pop("partner_account_id", None)
        request.session.pop("partner_auth_hash", None)
        return None
    return account


@never_cache
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("password")
def login(request):
    if current_partner(request):
        return redirect("partner_admin")
    error = ""
    status = 200
    if request.method == "POST":
        key = throttle.key_for(request)
        seconds = throttle.remaining(key)
        if seconds:
            error = "로그인 시도가 많습니다. 잠시 후 다시 시도해 주세요."
            status = 429
        else:
            username = request.POST.get("username", "")[:150]
            password = request.POST.get("password", "")
            account = PartnerAccount.objects.filter(username=username).first()
            valid = account.check_password(password) if account else False
            if account is None:
                make_password(password)
            if valid and account.is_active:
                throttle.clear(key)
                request.session.cycle_key()
                rotate_token(request)
                request.session["partner_account_id"] = account.pk
                request.session["partner_auth_hash"] = account.session_hash()
                account.last_login = timezone.now()
                account.save(update_fields=["last_login"])
                return redirect("partner_admin")
            throttle.failure(key)
            error = "아이디·비밀번호 또는 승인된 하위협력사 권한을 확인해 주세요."
            status = 400
    return render(request, "accounts/partner_admin.html", {"login_page": True, "error": error}, status=status)


@never_cache
@require_GET
def dashboard(request):
    partner = current_partner(request)
    if partner is None:
        return redirect("partner_admin_login")
    members = User.objects.filter(partner=partner)
    counts = {row["account_status"]:row["total"] for row in members.values("account_status").annotate(total=Count("pk"))}
    total = sum(counts.values())
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "")
    if query:
        members = members.filter(nickname__icontains=query)
    if status in User.Status.values:
        members = members.filter(account_status=status)
    else:
        status = ""
    page = Paginator(members.order_by("-date_joined", "-pk"), 20).get_page(request.GET.get("page"))
    return render(request, "accounts/partner_admin.html", {
        "partner": partner, "members": page, "query": query, "selected_status": status, "statuses": User.Status.choices,
        "total":total, "pending":counts.get("pending",0), "approved":counts.get("approved",0), "suspended":counts.get("suspended",0),
        "referral_link":request.build_absolute_uri("/")+"?ref="+partner.referral_code+"#/home",
    })


@never_cache
@require_POST
def logout(request):
    request.session.pop("partner_account_id", None)
    request.session.pop("partner_auth_hash", None)
    request.session.cycle_key()
    rotate_token(request)
    return redirect("partner_admin_login")
