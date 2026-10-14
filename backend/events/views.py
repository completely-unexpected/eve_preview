from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Event
def data(event):
    return {"id":event.pk,"title":event.title,"tag":event.tag,"summary":event.summary,"symbol":event.symbol}
@never_cache
@require_GET
def listing(request):
    return JsonResponse({"ok":True,"items":[data(event) for event in Event.objects.filter(is_published=True)]})
@never_cache
@require_GET
def detail(request,pk):
    event=get_object_or_404(Event,pk=pk,is_published=True)
    return JsonResponse({"ok":True,"event":{**data(event),"body":event.body}})
