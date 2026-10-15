from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from .forms import SignupForm, ProfileForm
from .models import User, PartnerAccount
from . import throttle
from inquiries.models import Inquiry


def login_limited(seconds):
    minutes = (seconds + 59) // 60
    response = JsonResponse({"ok": False, "message": f"로그인에 5회 실패하여 잠시 제한되었습니다. 약 {minutes}분 후 다시 시도해 주세요.", "retryAfter": seconds}, status=429)
    response["Retry-After"] = str(seconds)
    return response


def session_data(request):
    user = request.user
    return {
        "ok": True,
        "authenticated": user.is_authenticated,
        "user": {"username": user.username, "nickname": user.nickname, "joinedAt": user.date_joined.isoformat()}
        if user.is_authenticated else None,
        "unreadReplies": Inquiry.objects.filter(member=user,answer_read_at__isnull=True).exclude(answer="").count() if user.is_authenticated else 0,
        "csrfToken": get_token(request),
    }


@never_cache
@require_GET
def session(request):
    return JsonResponse(session_data(request))


@never_cache
@sensitive_post_parameters("password1", "password2")
@require_POST
@csrf_protect
def signup(request):
    if request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "가입하려면 먼저 로그아웃해 주세요."}, status=409)
    form = SignupForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    try:
        with transaction.atomic():
            user = form.save(commit=False)
            code = form.cleaned_data.get("referral_code")
            if code:
                partner = PartnerAccount.objects.select_for_update().filter(referral_code=code, is_active=True).first()
                if not partner:
                    return JsonResponse({"ok": False, "message": "사용할 수 없는 추천 코드입니다."}, status=400)
                user.partner = partner
            user.account_status = User.Status.PENDING
            user.save()
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "아이디가 이미 사용 중입니다. 다른 아이디를 입력해 주세요."}, status=409)
    data = session_data(request)
    data.update({"approvalRequired": True, "message": "가입 신청이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다."})
    return JsonResponse(data, status=201)


@never_cache
@sensitive_post_parameters("password")
@require_POST
@csrf_protect
def login(request):
    key = throttle.key_for(request)
    seconds = throttle.remaining(key)
    if seconds:
        return login_limited(seconds)
    form = AuthenticationForm(request, data=request.POST)
    if not form.is_valid():
        candidate = User.objects.filter(username=request.POST.get("username", "")).first()
        if candidate and not candidate.is_active and candidate.check_password(request.POST.get("password", "")):
            throttle.clear(key)
            if candidate.account_status == User.Status.PENDING:
                return JsonResponse({"ok": False, "message": "가입 승인 대기 중입니다. 관리자 승인 후 로그인해 주세요."}, status=403)
            if candidate.account_status == User.Status.SUSPENDED:
                return JsonResponse({"ok": False, "message": "이용이 정지된 계정입니다. 관리자에게 문의해 주세요."}, status=403)
        seconds = throttle.failure(key)
        if seconds:
            return login_limited(seconds)
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    throttle.clear(key)
    auth_login(request, form.get_user())
    return JsonResponse(session_data(request))


@never_cache
@require_POST
@csrf_protect
def logout(request):
    auth_logout(request)
    return JsonResponse(session_data(request))


@never_cache
@sensitive_post_parameters("old_password", "new_password1", "new_password2")
@require_POST
@csrf_protect
def password_change(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "로그인 후 비밀번호를 변경해 주세요."}, status=401)
    form = PasswordChangeForm(request.user, request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    user = form.save()
    update_session_auth_hash(request, user)
    data = session_data(request)
    data["message"] = "비밀번호가 변경되었습니다. 다른 기기에서는 다시 로그인해 주세요."
    return JsonResponse(data)


@never_cache
@require_POST
@csrf_protect
def profile(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "로그인 후 회원정보를 수정해 주세요."}, status=401)
    form = ProfileForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    request.user.nickname = form.cleaned_data["nickname"]
    request.user.save(update_fields=["nickname"])
    data = session_data(request)
    data["message"] = "닉네임이 변경되었습니다."
    return JsonResponse(data)


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/accounts/"):
        return JsonResponse({"ok": False, "message": "보안 확인이 만료되었습니다. 새로고침한 뒤 다시 시도해 주세요."}, status=403)
    return default_csrf_failure(request, reason=reason)


@never_cache
@require_GET
def details(request):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "message": "로그인 후 회원정보를 확인해 주세요."}, status=401)
    user = request.user
    level = user.level
    return JsonResponse({
        "ok": True,
        "user": {"username": user.username, "nickname": user.nickname, "joinedAt": user.date_joined.isoformat(),
                 "level": level.number if level else 1, "levelName": level.name if level else "기본", "status": user.get_account_status_display()},
        "limits": user.effective_limits(),
    })


@never_cache
@require_GET
def partner_members(request):
    from .partner_admin import current_partner
    partner = current_partner(request)
    if partner is None:
        return JsonResponse({"ok": False, "message": "협력사 전용 계정으로 로그인해 주세요."}, status=401)
    members = User.objects.filter(partner=partner).select_related("level").order_by("-date_joined", "-pk")
    search = request.GET.get("q", "").strip()[:100]
    if search:
        members = members.filter(nickname__icontains=search)
    status = request.GET.get("status", "")
    if status in User.Status.values:
        members = members.filter(account_status=status)
    page = Paginator(members, 20).get_page(request.GET.get("page"))
    return JsonResponse({"ok": True, "code": partner.referral_code,
        "items": [{"nickname": m.nickname or "닉네임 미설정", "status": m.account_status,
                   "statusLabel": m.get_account_status_display(), "level": m.level_id or 1,
                   "joinedAt": m.date_joined.isoformat()} for m in page],
        "page": page.number, "pages": page.paginator.num_pages, "total": page.paginator.count})
