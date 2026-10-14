from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from .models import Game
def data(game):
    return {"slug":game.slug,"name":game.name,"englishName":game.english_name,"category":game.category,"symbol":game.symbol,"description":game.description}
@never_cache
@require_GET
def listing(request):
    return JsonResponse({"ok":True,"items":[data(game) for game in Game.objects.filter(is_published=True)]})
@never_cache
@require_GET
def detail(request, slug):
    return JsonResponse({"ok":True,"game":data(get_object_or_404(Game,slug=slug,is_published=True))})
