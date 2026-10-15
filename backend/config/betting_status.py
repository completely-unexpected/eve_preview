from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from sportsfeed.models import DemoSlip


@require_GET
def summary(request):
    from .admin_metrics import totals
    return JsonResponse({'ok':True,'totals':totals(request.user)})


@require_GET
def betting_status(request):
    from django.db.models import Q
    if not (request.user.has_perm('sportsfeed.view_demoslip') or request.user.has_perm('sportsfeed.change_demoslip')): raise PermissionDenied
    slips=DemoSlip.objects.filter(status='pending').select_related('member').prefetch_related('results')
    query=request.GET.get('q','').strip();source=request.GET.get('source','')
    if query: slips=slips.filter(Q(member__username__icontains=query)|Q(member__nickname__icontains=query))
    if source in ('sports','powerball'): slips=slips.filter(source=source)
    summary_values=slips.aggregate(stake=Sum('total_stake'),expected=Sum('expected_return'))
    page=Paginator(slips,20).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    from sportsfeed.admin_history import ticket
    tickets=[ticket(slip,request.user.has_perm('sportsfeed.change_demoslip')) for slip in page]
    return render(request,'admin/betting_status.html',{**admin.site.each_context(request),'title':'배팅현황','page':page,'tickets':tickets,'query':query,'source':source,'page_query':params.urlencode(),'total':page.paginator.count,'stake_total':f"{summary_values['stake'] or 0:,}원",'expected_total':f"{summary_values['expected'] or 0:,}원"})
