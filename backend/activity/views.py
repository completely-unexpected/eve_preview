import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .tracking import record


@require_POST
def navigation(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok':False},status=401)
    route=request.POST.get('route','')
    if not re.fullmatch(r'#/(home|sports|inplay|esports|casino|games|events|inquiries|account|partner|oddsportal|board|wallet|attendance|notices|betting-history)(/[a-zA-Z0-9_-]{1,100})?',route):
        return JsonResponse({'ok':False},status=400)
    from .pages import page_name,touch
    touch(request.user.username,'admin' if request.user.is_staff else 'member',route,request.META.get('REMOTE_ADDR'))
    if request.POST.get('heartbeat')!='1':
        record('request',model='화면 이동',changes={'route':route,'screen':page_name(route),'reported_by':'browser'},status=200)
    return JsonResponse({'ok':True})
