from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django import forms
from django.utils import timezone
from .forms import InquiryForm
from .models import Inquiry

def summary(obj):
    return {"id": obj.pk, "title": obj.title, "answered": bool(obj.answer), "unread": bool(obj.answer) and obj.answer_read_at is None, "createdAt": obj.created_at.isoformat()}

def unauthorized():
    return JsonResponse({"ok": False, "message": "로그인 후 1:1 문의를 이용해 주세요."}, status=401)

@never_cache
@require_http_methods(["GET", "POST"])
@csrf_protect
def listing(request):
    if not request.user.is_authenticated:
        return unauthorized()
    if request.method == "POST":
        form = InquiryForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"ok": False, "errors": form.errors.get_json_data()}, status=400)
        obj = Inquiry.objects.create(member=request.user, **form.cleaned_data)
        return JsonResponse({"ok": True, "inquiry": summary(obj)}, status=201)
    page = Paginator(Inquiry.objects.filter(member=request.user), 20).get_page(request.GET.get("page"))
    return JsonResponse({"ok": True, "items": [summary(obj) for obj in page], "page": page.number, "pages": page.paginator.num_pages})

@never_cache
@require_GET
def detail(request, pk):
    if not request.user.is_authenticated:
        return unauthorized()
    obj = get_object_or_404(Inquiry, pk=pk, member=request.user)
    return JsonResponse({"ok": True, "inquiry": {**summary(obj), "body": obj.body, "answer": obj.answer, "answeredAt": obj.answered_at.isoformat() if obj.answered_at else None}})


class ReadAnswerForm(forms.Form):
    answered_at = forms.DateTimeField(required=False)

@never_cache
@require_POST
@csrf_protect
def read_answer(request, pk):
    if not request.user.is_authenticated:
        return unauthorized()
    obj = get_object_or_404(Inquiry, pk=pk, member=request.user)
    form = ReadAnswerForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok":False},status=400)
    # Only acknowledge the exact answer the browser displayed. A newer edit stays unread.
    Inquiry.objects.filter(pk=obj.pk, member=request.user, answered_at=form.cleaned_data["answered_at"], answer_read_at__isnull=True).exclude(answer="").update(answer_read_at=timezone.now())
    return JsonResponse({"ok":True})
