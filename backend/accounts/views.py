from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.csrf import csrf_failure as default_csrf_failure
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_POST

from .forms import SignupForm


def session_data(request):
    user = request.user
    return {
        "ok": True,
        "authenticated": user.is_authenticated,
        "user": {"username": user.username, "nickname": user.nickname}
        if user.is_authenticated else None,
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
            user = form.save()
    except IntegrityError:
        return JsonResponse({"ok": False, "message": "아이디가 이미 사용 중입니다. 다른 아이디를 입력해 주세요."}, status=409)
    auth_login(request, user)
    return JsonResponse(session_data(request), status=201)


@never_cache
@sensitive_post_parameters("password")
@require_POST
@csrf_protect
def login(request):
    form = AuthenticationForm(request, data=request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
    auth_login(request, form.get_user())
    return JsonResponse(session_data(request))


@never_cache
@require_POST
@csrf_protect
def logout(request):
    auth_logout(request)
    return JsonResponse(session_data(request))


def csrf_failure(request, reason=""):
    if request.path.startswith("/api/accounts/"):
        return JsonResponse({"ok": False, "message": "보안 확인이 만료되었습니다. 새로고침한 뒤 다시 시도해 주세요."}, status=403)
    return default_csrf_failure(request, reason=reason)
