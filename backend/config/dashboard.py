from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from inquiries.models import Inquiry

@require_GET
def overview(request):
    cards = []
    user_model = get_user_model()
    user_admin = admin.site._registry[user_model]
    if user_admin.has_view_permission(request):
        totals = user_model.objects.aggregate(total=Count("pk"), pending=Count("pk",filter=Q(account_status="pending")), suspended=Count("pk",filter=Q(account_status="suspended")))
        link = reverse("admin:accounts_user_changelist")
        cards.extend([
            {"label":"전체 회원", "count":totals["total"], "url":link},
            {"label":"승인 대기", "count":totals["pending"], "url":link+"?account_status__exact=pending"},
            {"label":"이용 정지", "count":totals["suspended"], "url":link+"?account_status__exact=suspended"},
        ])
    inquiry_admin = admin.site._registry[Inquiry]
    if inquiry_admin.has_view_permission(request):
        totals = Inquiry.objects.aggregate(total=Count("pk"), pending=Count("pk",filter=Q(answer="")))
        link = reverse("admin:inquiries_inquiry_changelist")
        cards.extend([
            {"label":"전체 문의", "count":totals["total"], "url":link},
            {"label":"답변 대기 문의", "count":totals["pending"], "url":link+"?answer__exact="},
        ])
    context = {**admin.site.each_context(request), "title":"관리자 현황", "cards":cards}
    return render(request,"admin/overview.html",context)
