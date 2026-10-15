from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from .models import FeedSnapshot
from .collector import collect
from .services import ProviderError

@admin.register(FeedSnapshot)
class FeedSnapshotAdmin(admin.ModelAdmin):
    list_display = ["__str__", "fetched_at", "syncing", "last_error"]
    readonly_fields = ["fetched_at", "syncing", "started_at", "last_error"]
    fields = readonly_fields
    actions = ["refresh_feed"]
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
    @admin.action(description="전체 경기·배당 다시 조회 (크레딧 사용)", permissions=["change"])
    def refresh_feed(self, request, queryset):
        try:
            snapshot = collect(force=True)
            self.message_user(request, f"{len(snapshot.payload.get('items', []))}개 경기 조회. 남은 크레딧: {snapshot.payload.get('remainingCredits')}")
        except ProviderError as exc:
            self.message_user(request, str(exc), messages.ERROR)


from django.core.exceptions import ValidationError
from django.db import OperationalError
from .models import DemoLeg, DemoSlip
from .settlement import settle


class SettlementActions:
    actions = ['mark_won', 'mark_lost', 'mark_void']
    def has_settle_permission(self, request):
        return request.user.is_active and request.user.is_staff and request.user.has_perm('sportsfeed.change_demoslip')
    def process(self, request, queryset, result):
        done = 0
        for obj in queryset.order_by('pk'):
            try:
                done += settle(obj.slip_id if isinstance(obj, DemoLeg) else obj.pk, request.user,
                               result=result, position=obj.position if isinstance(obj, DemoLeg) else None)
            except (ValidationError, OperationalError) as exc:
                message = exc.messages[0] if isinstance(exc, ValidationError) else '동시 처리 중입니다. 잠시 후 다시 시도해 주세요.'
                self.message_user(request, f'#{obj.pk}: {message}', messages.ERROR)
        self.message_user(request, f'{done}개 경기 결과 처리 완료. 같은 결과는 중복 지급하지 않습니다.')
    @admin.action(description='남은 결과 적중 처리', permissions=['settle'])
    def mark_won(self, request, queryset): self.process(request, queryset, 'won')
    @admin.action(description='남은 결과 미적중 처리', permissions=['settle'])
    def mark_lost(self, request, queryset): self.process(request, queryset, 'lost')
    @admin.action(description='남은 결과 취소·복원 처리', permissions=['settle'])
    def mark_void(self, request, queryset): self.process(request, queryset, 'void')


@admin.register(DemoSlip)
class DemoSlipAdmin(SettlementActions, admin.ModelAdmin):
    change_list_template='admin/sportsfeed/demoslip_list.html'
    change_form_template='admin/sportsfeed/demoslip_detail.html'
    list_display = ['id', 'member', 'source', 'mode', 'status', 'total_stake', 'expected_return', 'credited_amount', 'created_at', 'settled_at']
    list_filter = ['source', 'status', 'mode', 'created_at']
    search_fields = ['member__username', 'member__nickname']
    readonly_fields = [f.name for f in DemoSlip._meta.fields]
    fields=['id','member','source','mode','status','created_at','settled_at','settled_by']
    list_per_page=20
    def get_action_choices(self,request,default_choices=None):
        return [('', '작업 선택')]+[(value,label) for value,label in super().get_action_choices(request) if value]
    def get_queryset(self,request):
        queryset=super().get_queryset(request).select_related('member').prefetch_related('results')
        match=getattr(request,'resolver_match',None)
        if match and match.url_name=='sportsfeed_demoslip_changelist' and not request.GET.get('status__exact'):
            queryset=queryset.exclude(status='void')
        return queryset
    def get_urls(self):
        from django.urls import path
        return [path('<int:slip_id>/settle/',self.admin_site.admin_view(self.settle_one),name='sportsfeed_demoslip_settle')]+super().get_urls()
    def settle_one(self,request,slip_id):
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import get_object_or_404,redirect
        from django.contrib.admin.models import LogEntry,CHANGE
        from django.contrib.contenttypes.models import ContentType
        if request.method!='POST': return HttpResponseNotAllowed(['POST'])
        if not self.has_settle_permission(request): raise PermissionDenied
        obj=get_object_or_404(DemoSlip,pk=slip_id)
        result=request.POST.get('result')
        if result not in ('lost','void'):
            self.message_user(request,'취소 또는 낙첨을 선택하세요.',messages.ERROR)
            return redirect('admin:sportsfeed_demoslip_change',slip_id)
        cancelled=False
        try:
            count=settle(obj.pk,request.user,result=result)
            obj.refresh_from_db(fields=['status'])
            cancelled=result=='void' and obj.status!='pending' and (count>0 or obj.status=='void')
            if count:
                label='배팅 취소·미정산 선택 환급' if result=='void' else '배팅 낙첨 처리'
                LogEntry.objects.create(user=request.user,content_type=ContentType.objects.get_for_model(DemoSlip),object_id=str(obj.pk),object_repr=f'배팅 #{obj.pk}',action_flag=CHANGE,change_message=label)
                self.message_user(request,label+' 완료')
            else: self.message_user(request,'이미 처리된 내역입니다. 중복 처리하지 않았습니다.',messages.WARNING)
        except (ValidationError,OperationalError) as exc:
            self.message_user(request,exc.messages[0] if isinstance(exc,ValidationError) else '다른 처리가 진행 중입니다. 잠시 후 다시 시도하세요.',messages.ERROR)
        if cancelled:
            if request.GET.get('next')=='/admin/betting-status/': return redirect('/admin/betting-status/')
            return redirect('admin:sportsfeed_demoslip_changelist')
        return redirect('admin:sportsfeed_demoslip_change',slip_id)
    def changelist_view(self,request,extra_context=None):
        response=super().changelist_view(request,extra_context)
        if getattr(response,'context_data',None) and 'cl' in response.context_data:
            from .admin_history import ticket
            response.context_data['tickets']=[ticket(obj,self.has_settle_permission(request)) for obj in response.context_data['cl'].result_list]
        return response
    def change_view(self,request,object_id,form_url='',extra_context=None):
        from .admin_history import ticket
        obj=self.get_object(request,object_id)
        return super().change_view(request,object_id,form_url,{**(extra_context or {}),'ticket':ticket(obj,self.has_settle_permission(request)) if obj else None})
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(DemoLeg)
class DemoLegAdmin(SettlementActions, admin.ModelAdmin):
    list_display = ['__str__', 'member', 'selection_name', 'result', 'settled_at', 'settled_by']
    list_filter = ['result', 'slip__mode']
    search_fields = ['slip__member__username', 'slip__member__nickname']
    list_select_related = ['slip__member', 'settled_by']
    readonly_fields = [f.name for f in DemoLeg._meta.fields]
    @admin.display(description='회원')
    def member(self, obj): return obj.slip.member.nickname or obj.slip.member.username
    @admin.display(description='선택 항목')
    def selection_name(self, obj):
        return f"{obj.selection.get('market', '')} · {obj.selection.get('name', '')} · {obj.selection.get('point') or ''} @{obj.selection.get('price', '')}"
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


from .models import PowerballResult, PowerballSync

@admin.register(PowerballResult)
class PowerballResultAdmin(admin.ModelAdmin):
    list_display=['day','round_number','balls','general_total','general_parity','general_range','powerball','power_parity','power_range','received_at']
    list_filter=['day']
    readonly_fields=[f.name for f in PowerballResult._meta.fields]+['general_total','general_parity','general_range','power_parity','power_range']
    @admin.display(description='일반볼 합계')
    def general_total(self,obj): return sum(obj.balls)
    @admin.display(description='일반볼 홀/짝')
    def general_parity(self,obj):
        from .powerball_outcomes import outcomes
        return outcomes(obj)['general_parity']
    @admin.display(description='일반볼 대/중/소')
    def general_range(self,obj):
        from .powerball_outcomes import outcomes
        return outcomes(obj)['general_range']
    @admin.display(description='파워볼 홀/짝')
    def power_parity(self,obj):
        from .powerball_outcomes import outcomes
        return outcomes(obj)['power_parity']
    @admin.display(description='파워볼 언더/오버')
    def power_range(self,obj):
        from .powerball_outcomes import outcomes
        return outcomes(obj)['power_range']
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False

@admin.register(PowerballSync)
class PowerballSyncAdmin(admin.ModelAdmin):
    list_display=['__str__','enabled','fetched_at','last_error']
    fields=['enabled','fetched_at','last_error']
    readonly_fields=['fetched_at','last_error']
    def has_delete_permission(self,request,obj=None): return False
    def has_add_permission(self,request): return not PowerballSync.objects.exists()


from .models import OddsPortalSnapshot

@admin.register(OddsPortalSnapshot)
class OddsPortalSnapshotAdmin(admin.ModelAdmin):
    change_list_template = 'admin/sportsfeed/oddsportal_collection.html'
    list_display = ("__str__", "fetched_at", "last_error")
    readonly_fields = ("payload", "fetched_at", "last_error")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

    def get_urls(self):
        from django.urls import path
        return [path('toggle-results/',self.admin_site.admin_view(self.toggle_results),name='sportsfeed_oddsportal_toggle_results'),
                path('collect-today/',self.admin_site.admin_view(self.collect_today),name='sportsfeed_oddsportal_collect_today'),
                path('collection-status/<int:job_id>/',self.admin_site.admin_view(self.collection_status),name='sportsfeed_oddsportal_collection_status')]+super().get_urls()

    def toggle_results(self, request):
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import redirect
        from .collector_control import set_paused
        if request.method != 'POST': return HttpResponseNotAllowed(['POST'])
        if not self.has_change_permission(request): raise PermissionDenied
        paused = request.POST.get('action') != 'resume'
        set_paused(paused)
        self.message_user(request, '결과 자동 수집을 중지했습니다.' if paused else '결과 자동 수집을 재개했습니다.')
        return redirect('admin:sportsfeed_oddsportalsnapshot_changelist')

    def collect_today(self, request):
        from django.http import HttpResponseNotAllowed
        from django.shortcuts import redirect
        from .oddsportal_jobs import start_job
        from .parsing_options import ParsingForm
        if request.method!='POST': return HttpResponseNotAllowed(['POST'])
        if not self.has_change_permission(request): raise PermissionDenied
        defaults={'sport':'all','league':'all','status':'all','odds':'all','limit':'0'}
        form=ParsingForm({key:request.POST.get(key,value) for key,value in defaults.items()})
        if not form.is_valid():
            self.message_user(request,form.errors.as_text(),messages.ERROR)
            return redirect('admin:sportsfeed_oddsportalsnapshot_changelist')
        job,started=start_job(request.user,form.cleaned_data)
        if job.status=='failed':
            self.message_user(request,'수집을 시작하지 못했습니다. '+job.error,messages.ERROR)
        else:
            self.message_user(request,'오늘 경기 전체 수집을 시작했습니다.' if started else '이미 수집이 진행 중입니다. 중복 실행하지 않았습니다.',messages.SUCCESS if started else messages.WARNING)
        return redirect('admin:sportsfeed_oddsportalsnapshot_changelist')

    def collection_status(self, request, job_id):
        from django.http import JsonResponse
        from django.shortcuts import get_object_or_404
        from .models import OddsPortalCollectionJob
        from .oddsportal_jobs import expire_stale, serialize
        from .parsing_options import ParsingForm
        if request.method!='GET':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET'])
        if not self.has_view_or_change_permission(request): raise PermissionDenied
        expire_stale()
        return JsonResponse(serialize(get_object_or_404(OddsPortalCollectionJob,pk=job_id)))

    def changelist_view(self, request, extra_context=None):
        from django.urls import reverse
        from .models import OddsPortalCollectionJob
        from .oddsportal_jobs import expire_stale, serialize
        from .parsing_options import ParsingForm
        expire_stale()
        job=OddsPortalCollectionJob.objects.first()
        return super().changelist_view(request,{**(extra_context or {}),
            'parsing_form':ParsingForm(),
            'title':'OddsParsing 수집 실행',
            'results_paused':__import__('sportsfeed.collector_control',fromlist=['is_paused']).is_paused(),
            'toggle_results_url':reverse('admin:sportsfeed_oddsportal_toggle_results'),
            'can_collect':self.has_change_permission(request),
            'collect_url':reverse('admin:sportsfeed_oddsportal_collect_today'),
            'collection_job':serialize(job) if job else None,
            'collection_status_url':reverse('admin:sportsfeed_oddsportal_collection_status',args=[job.pk]) if job else '',
        })


from .models import OddsPortalCollectionJob

@admin.register(OddsPortalCollectionJob)
class OddsPortalCollectionJobAdmin(admin.ModelAdmin):
    list_display=('id','day','status','pages_done','pages_total','match_count','requested_by','created_at','finished_at')
    readonly_fields=[field.name for field in OddsPortalCollectionJob._meta.fields]
    exclude=('active_key',)
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False


from .models import HarvesterSnapshot, HarvesterJob

@admin.register(HarvesterSnapshot)
class HarvesterSnapshotAdmin(admin.ModelAdmin):
    def has_add_permission(self,request): return False
    def has_delete_permission(self,request,obj=None): return False

    def get_urls(self):
        from django.urls import path
        return [path('inplay/',self.admin_site.admin_view(self.inplay_view),name='sportsfeed_inplay_collect')]+super().get_urls()
    def inplay_view(self,request): return self.collection_view(request,inplay=True)
    def changelist_view(self,request,extra_context=None): return self.collection_view(request)
    def collection_view(self,request,inplay=False):
        from .harvester import CollectionForm, InplayForm, start_job, expire_stale
        from .models import InplaySnapshot
        from django.shortcuts import redirect
        from django.template.response import TemplateResponse
        from django.utils import timezone
        if not self.has_view_or_change_permission(request): raise PermissionDenied
        expire_stale()
        form=(InplayForm if inplay else CollectionForm)(request.POST if request.method=='POST' and request.POST.get('action')=='collect' else None)
        scoped=HarvesterJob.objects.filter(mode='live') if inplay else HarvesterJob.objects.exclude(mode='live')
        if request.method=='POST':
            if not self.has_change_permission(request): raise PermissionDenied
            if request.POST.get('action')=='stop':
                scoped.filter(active_key='harvester').update(status='cancelled',active_key=None,error='관리자가 중지했습니다.',finished_at=timezone.now())
                self.message_user(request,'Harvester 수집 중지를 요청했습니다. 기존 수집기는 계속 동작합니다.')
                return redirect(request.path)
            if form.is_valid():
                job,started=start_job(request.user,form.cleaned_data)
                self.message_user(request,'Harvester 수집을 시작했습니다.' if started else 'Harvester 수집이 이미 진행 중입니다.')
                return redirect(request.path)
        state=(InplaySnapshot if inplay else HarvesterSnapshot).objects.filter(pk=1).first()
        return TemplateResponse(request,'admin/sportsfeed/harvester.html',{**self.admin_site.each_context(request),'opts':self.model._meta,'title':'Inplay 수집 실행' if inplay else 'OddsHarvester 수집 실행','inplay':inplay,'source':'inplay' if inplay else 'harvester','form':form,'jobs':scoped.select_related('requested_by')[:15],'active':scoped.filter(active_key='harvester').exists(),'busy':HarvesterJob.objects.filter(active_key='harvester').exists(),'can_collect':self.has_change_permission(request),'snapshot':state,'count':len(state.payload.get('items',[])) if state else 0})

    def change_view(self,request,object_id,form_url='',extra_context=None):
        from django.shortcuts import redirect
        return redirect('admin:sportsfeed_harvestersnapshot_changelist')


@admin.register(HarvesterJob)
class HarvesterJobAdmin(admin.ModelAdmin):
    list_display=('id','sport','mode','target_bookmaker','status','match_count','requested_by','created_at','finished_at')
    readonly_fields=[field.name for field in HarvesterJob._meta.fields]
    exclude=('active_key',)
    def get_queryset(self,request):
        queryset=super().get_queryset(request)
        match=getattr(request,'resolver_match',None)
        if match and match.url_name=='sportsfeed_harvesterjob_changelist' and request.GET.get('mode__exact')!='live': queryset=queryset.exclude(mode='live')
        return queryset
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
