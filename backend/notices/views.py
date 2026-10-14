from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Notice

def data(notice):
    return {"id": notice.pk, "title": notice.title, "pinned": notice.is_pinned, "createdAt": notice.created_at.isoformat(), "updatedAt": notice.updated_at.isoformat()}

@never_cache
@require_GET
def listing(request):
    page = Paginator(Notice.objects.filter(is_published=True), 20).get_page(request.GET.get("page"))
    return JsonResponse({"ok": True, "items": [data(n) for n in page], "page": page.number, "pages": page.paginator.num_pages, "count": page.paginator.count})

@never_cache
@require_GET
def detail(request, pk):
    notice = get_object_or_404(Notice, pk=pk, is_published=True)
    return JsonResponse({"ok": True, "notice": {**data(notice), "body": notice.body}})
