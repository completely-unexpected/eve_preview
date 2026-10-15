from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
from django.contrib import admin
from django.db.models import OuterRef,Subquery,Sum,BigIntegerField,Value,F
from django.db.models.functions import Coalesce
from django.utils import timezone


def member_metrics(queryset):
    from wallet.models import Wallet,MoneyRequest
    from sportsfeed.models import DemoSlip
    from activity.models import PagePresence
    today=timezone.now().astimezone(ZoneInfo('Asia/Seoul')).date()
    start=datetime.combine(today,time.min,tzinfo=ZoneInfo('Asia/Seoul'));end=start+timedelta(days=1)
    def summed(query,expression):
        query=query.order_by().values('member_id').annotate(total=Sum(expression)).values('total')[:1]
        return Coalesce(Subquery(query,output_field=BigIntegerField()),Value(0),output_field=BigIntegerField())
    requests=MoneyRequest.objects.filter(member_id=OuterRef('pk'),status='approved')
    slips=DemoSlip.objects.filter(member_id=OuterRef('pk'))
    wallets=Wallet.objects.filter(member_id=OuterRef('pk'))
    return queryset.select_related('partner','referrer').annotate(
        metric_money=Coalesce(Subquery(wallets.values('available')[:1]),Value(0),output_field=BigIntegerField()),
        metric_points=Coalesce(Subquery(wallets.values('points')[:1]),Value(0),output_field=BigIntegerField()),
        metric_deposit=summed(requests.filter(kind='deposit'),'amount'),
        metric_withdraw=summed(requests.filter(kind='withdraw'),'amount'),
        metric_today_deposit=summed(requests.filter(kind='deposit',processed_at__gte=start,processed_at__lt=end),'amount'),
        metric_today_withdraw=summed(requests.filter(kind='withdraw',processed_at__gte=start,processed_at__lt=end),'amount'),
        metric_bets=summed(slips.filter(created_at__gte=start,created_at__lt=end),'total_stake'),
        metric_profit=summed(slips.filter(settled_at__gte=start,settled_at__lt=end).exclude(status='pending'),F('credited_amount')-F('total_stake')),
        metric_last_seen=Subquery(PagePresence.objects.filter(actor=OuterRef('username'),actor_kind__in=['member','admin']).order_by('-last_seen').values('last_seen')[:1]),
    )


class MemberColumns:
    member_columns=('member_username','member_nickname','member_partner','member_wallet_name','member_last_seen','member_money','member_points','member_lifetime','member_today_deposit','member_today_withdraw','member_bets','member_profit','member_referrer')
    def person(self,obj): return obj if hasattr(obj,'username') else obj.member
    def amount(self,obj,field): return f'{getattr(self.person(obj),field,0):,}'
    @admin.display(description='아이디')
    def member_username(self,obj): return self.person(obj).username
    @admin.display(description='닉네임')
    def member_nickname(self,obj): return self.person(obj).nickname or '—'
    @admin.display(description='소속(하위협력사)')
    def member_partner(self,obj): return self.person(obj).partner or '—'
    @admin.display(description='지갑명')
    def member_wallet_name(self,obj): return self.person(obj).wallet_name
    @admin.display(description='최종접속시간')
    def member_last_seen(self,obj):
        user=self.person(obj);dates=[value for value in (user.metric_last_seen,user.last_login) if value]
        return timezone.localtime(max(dates),ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S') if dates else '—'
    @admin.display(description='보유머니')
    def member_money(self,obj): return self.amount(obj,'metric_money')
    @admin.display(description='보유포인트')
    def member_points(self,obj): return self.amount(obj,'metric_points')
    @admin.display(description='누적충전 / 누적환전')
    def member_lifetime(self,obj): return self.amount(obj,'metric_deposit')+' / '+self.amount(obj,'metric_withdraw')
    @admin.display(description='당일충전')
    def member_today_deposit(self,obj): return self.amount(obj,'metric_today_deposit')
    @admin.display(description='당일환전')
    def member_today_withdraw(self,obj): return self.amount(obj,'metric_today_withdraw')
    @admin.display(description='당일배팅')
    def member_bets(self,obj): return self.amount(obj,'metric_bets')
    @admin.display(description='수익금')
    def member_profit(self,obj): return self.amount(obj,'metric_profit')
    @admin.display(description='추천인')
    def member_referrer(self,obj):
        user=self.person(obj).referrer
        return f'{user.username} ({user.nickname})' if user and user.nickname else user.username if user else '—'
