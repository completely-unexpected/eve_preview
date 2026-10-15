from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
from django.db.models import Sum,Q,Count
from django.utils import timezone
from wallet.models import Wallet,MoneyRequest


def totals(user):
    result={}
    if user.has_perm('wallet.view_wallet') or user.has_perm('wallet.change_wallet'):
        result['balance']=Wallet.objects.filter(member__is_staff=False).aggregate(value=Sum('available'))['value'] or 0
    if user.has_perm('wallet.view_moneyrequest') or user.has_perm('wallet.change_moneyrequest'):
        zone=ZoneInfo('Asia/Seoul');today=timezone.now().astimezone(zone).date()
        start=datetime.combine(today,time.min,tzinfo=zone);end=start+timedelta(days=1)
        amounts=MoneyRequest.objects.filter(member__is_staff=False,status='approved',processed_at__gte=start,processed_at__lt=end).aggregate(
            deposit=Sum('amount',filter=Q(kind='deposit')),withdraw=Sum('amount',filter=Q(kind='withdraw')))
        result.update(deposit=amounts['deposit'] or 0,withdraw=amounts['withdraw'] or 0)
        pending=MoneyRequest.objects.filter(member__is_staff=False,status='pending').aggregate(
            pending_deposit=Count('pk',filter=Q(kind='deposit')),pending_withdraw=Count('pk',filter=Q(kind='withdraw')))
        result.update(pending)
    return {key:{'value':value,'display':f'{value:,}'+('건' if key.startswith('pending_') else '원')} for key,value in result.items()}
