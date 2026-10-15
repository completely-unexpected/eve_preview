from decimal import Decimal
from django import forms
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from .models import ManualOdds
from .odds import managed_events, choices, apply_prices, row_display, finished, display_price


def lock_current_event(source, event_id, fallback):
    from sportsfeed.models import FeedSnapshot, OddsPortalSnapshot, HarvesterSnapshot, InplaySnapshot
    model = {'sports': FeedSnapshot, 'oddsportal': OddsPortalSnapshot, 'harvester':HarvesterSnapshot,'inplay':InplaySnapshot}.get(source)
    if model:
        state = model.objects.select_for_update().filter(pk=1).first()
        return next((event for event in state.payload.get('items', []) if str(event['id']) == event_id), None) if state else None
    return next((row['event'] for row in managed_events() if row['source'] == source and str(row['event']['id']) == event_id), None)


def manage(model_admin, request):
    if not model_admin.has_view_or_change_permission(request):
        raise PermissionDenied
    source, event_id = request.GET.get('source', ''), request.GET.get('event', '')
    rows = managed_events()
    results = request.GET.get('status') == 'results'
    context = {**model_admin.admin_site.each_context(request), 'opts': model_admin.model._meta, 'title': '경기결과' if results else '경기·배당 전체 조회', 'results': results}
    from sportsfeed.models import FeedSnapshot
    from sportsfeed.portal_bridge import eligible
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    feed=FeedSnapshot.objects.filter(pk=1).first()
    if feed and feed.payload.get('lastResultBridge'):
        context.update(bridge_closed=sum(bool(event.get('completed') and event.get('resultSource',{}).get('provider')=='OddsPortal') for event in feed.payload.get('items',[])),bridge_pending=sum(eligible(event,timezone.now()) for event in feed.payload.get('items',[])),bridge_at=parse_datetime(feed.payload['lastResultBridge']['at']))
    if event_id:
        row = next((row for row in rows if row['source'] == source and str(row['event']['id']) == event_id), None)
        if not row:
            raise Http404('현재 목록에 없는 경기입니다.')
        if request.method == 'POST' and request.POST.get('inline') == '1':
            if not model_admin.has_change_permission(request): raise PermissionDenied
            field = forms.DecimalField(required=False, min_value=Decimal('1.0001'), max_value=Decimal('1000000'), decimal_places=4, max_digits=11)
            try:
                value = field.clean(request.POST.get('value', ''))
            except forms.ValidationError as exc:
                return JsonResponse({'message': exc.messages[0]}, status=400)
            key = request.POST.get('key', '')
            with transaction.atomic():
                current = lock_current_event(source, event_id, row['event'])
                if not current or finished(current): return JsonResponse({'message': '완료된 경기의 배당은 수정할 수 없습니다. 경기결과에서 확인하세요.'}, status=409)
                if key not in {choice[0] for choice in choices(current, source)}: return JsonResponse({'message':'배당 항목이 변경되었습니다. 새로고침해 주세요.'}, status=409)
                obj, _ = ManualOdds.objects.select_for_update().get_or_create(source=source, event_id=event_id, defaults={'updated_by':request.user})
                values = dict(obj.prices)
                if value is None: values.pop(key, None)
                else: values[key] = format(value, '.4f')
                obj.prices = values; obj.updated_by = request.user; obj.save()
                LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(ManualOdds), object_id=str(obj.pk), object_repr=f'{source}: {event_id}'[:200], action_flag=CHANGE, change_message='배당 셀 수정: '+key)
                effective = apply_prices([current], source)[0]
                price = next(choice[2] for choice in choices(effective, source) if choice[0] == key)
            return JsonResponse({'ok':True, 'price':display_price(price)})
        saved = ManualOdds.objects.filter(source=source, event_id=event_id).first()
        prices = saved.prices if saved else {}
        fields = {}
        for key, label, price, container, index in choices(row['event'], source):
            try:
                initial = Decimal(str(price))
                if not initial.is_finite(): initial = None
            except Exception:
                initial = None
            fields['odd_' + key] = forms.DecimalField(label=label, required=False, min_value=Decimal('1.0001'), max_value=Decimal('1000000'), decimal_places=4, max_digits=11, initial=prices.get(key), help_text=f'수집 배당: {initial if initial is not None else "없음"} · 비우면 수집 배당 적용')
        form = type('OddsForm', (forms.Form,), fields)(request.POST if request.method == 'POST' else None)
        if request.method == 'POST':
            if not model_admin.has_change_permission(request): raise PermissionDenied
            if finished(row['event']): return JsonResponse({'message':'완료된 경기의 배당은 수정할 수 없습니다.'}, status=409)
            if form.is_valid():
                values = {key[4:]: format(value, '.4f') for key, value in form.cleaned_data.items() if value is not None}
                with transaction.atomic():
                    current = lock_current_event(source, event_id, row['event'])
                    if not current or finished(current): return JsonResponse({'message':'완료된 경기의 배당은 수정할 수 없습니다.'}, status=409)
                    obj, _ = ManualOdds.objects.update_or_create(source=source, event_id=event_id, defaults={'prices': values, 'updated_by': request.user})
                    LogEntry.objects.create(user=request.user, content_type=ContentType.objects.get_for_model(ManualOdds), object_id=str(obj.pk), object_repr=f'{source}: {event_id}'[:200], action_flag=CHANGE, change_message='수동 배당 수정: '+str(len(values))+'개')
                messages.success(request, '배당을 저장했습니다. 홈페이지의 다음 조회부터 반영됩니다.')
                return redirect(request.get_full_path())
        if finished(row['event']):
            for field in form.fields.values(): field.disabled = True
        context.update(row=row, form=form, can_edit=model_admin.has_change_permission(request) and not finished(row['event']), saved=saved)
    else:
        query = request.GET.get('q', '').strip()
        awaiting=request.GET.get('status')=='awaiting'
        status = 'results' if results else 'awaiting' if awaiting else 'active'
        if source: rows = [row for row in rows if row['source'] == source]
        rows = [row for row in rows if finished(row['event']) == results]
        if awaiting: rows=[row for row in rows if row['source']=='sports' and eligible(row['event'],timezone.now())]
        sports = sorted({(row['event']['sportKey'], row['event']['sportLabel']) for row in rows}, key=lambda item:item[1])
        sport = request.GET.get('sport', '')
        league = request.GET.get('league', '')
        if sport: rows = [row for row in rows if row['event']['sportKey'] == sport]
        leagues = sorted({(str(row['event'].get('leagueKey') or row['event'].get('league', '')), row['event'].get('league') or '리그 미확인') for row in rows}, key=lambda item:item[1])
        if league: rows = [row for row in rows if str(row['event'].get('leagueKey') or row['event'].get('league', '')) == league]
        if query: rows = [row for row in rows if query.casefold() in ' '.join(str(row['event'].get(key, '')) for key in ('home', 'away', 'league', 'leagueOriginal', 'id')).casefold()]
        overrides = set(ManualOdds.objects.exclude(prices={}).values_list('source', 'event_id'))
        effective_rows = {}
        for kind in {row['source'] for row in rows}:
            effective_rows[kind] = {str(event['id']): event for event in apply_prices([row['event'] for row in rows if row['source'] == kind], kind)}
        for row in rows:
            effective = effective_rows[row['source']][str(row['event']['id'])]
            if effective.get('powerballResult'):
                result=row['event']['powerballResult']
                for book in effective.get('bookmakers',[]):
                    for market in book.get('markets',[]):
                        result[market['key']+'_choices']=[{'name':outcome['name'],'price':display_price(outcome['price']),'winner':outcome['name']==result.get(market['key'])} for outcome in market.get('outcomes',[])]
            row['display'] = row_display(effective, row['source'])
            row['manual'] = (row['source'], str(row['event']['id'])) in overrides
            row['can_edit'] = model_admin.has_change_permission(request) and not finished(row['event'])
            row['edit_url'] = reverse('admin:catalog_game_odds') + '?' + __import__('urllib.parse', fromlist=['urlencode']).urlencode({'source': row['source'], 'event': row['event']['id']})
        page = Paginator(rows, 20).get_page(request.GET.get('page'))
        params = request.GET.copy(); params.pop('page', None)
        context.update(page=page, query=query, source=source, status=status, page_query=params.urlencode(), total=len(rows), sports=sports, leagues=leagues, sport=sport, league=league,powerball_results=results and (source=='powerball' or sport=='powerball'))
    return TemplateResponse(request, 'admin/catalog/game/odds.html', context)
