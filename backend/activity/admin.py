import json
from django.contrib import admin
from django.utils.html import format_html
from .models import ActivityLog, PagePresence
from .pages import page_name


@admin.register(PagePresence)
class PagePresenceAdmin(admin.ModelAdmin):
    change_list_template='admin/activity/presence.html'
    list_display=('actor','actor_kind','screen','online','last_seen')
    list_filter=('actor_kind','last_seen')
    search_fields=('actor','route')
    readonly_fields=('actor','actor_kind','screen','online','last_seen','route')
    list_per_page=50
    @admin.display(description='현재 머무는 화면')
    def screen(self,obj): return page_name(obj.route)
    @admin.display(description='접속 상태')
    def online(self,obj):
        from django.utils import timezone
        from datetime import timedelta
        return '활동 중' if obj.last_seen>=timezone.now()-timedelta(seconds=90) else '최근 활동 없음'
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display=('created_at','actor','actor_kind','action','screen','target_name','target_id','method','path','status_code')
    list_filter=('actor_kind','action','target_model','status_code','created_at')
    search_fields=('actor','target_model','target_id','path','=request_id')
    date_hierarchy='created_at'
    list_per_page=50
    readonly_fields=('created_at','request_id','actor','actor_kind','action','path','method','status_code','target_model','target_id','details')
    exclude=('changes',)
    @admin.display(description='이용 화면')
    def screen(self,obj):
        route=obj.changes.get('route') if isinstance(obj.changes,dict) else None
        return page_name(route) if route else page_name(obj.path) if obj.path.startswith(('/admin/','/partner-admin/')) else ''

    @admin.display(description='대상 종류')
    def target_name(self,obj):
        from django.apps import apps
        try: return str(apps.get_model(obj.target_model)._meta.verbose_name)
        except (LookupError,ValueError): return obj.target_model

    @admin.display(description='변경 전후·처리 정보')
    def details(self,obj):
        return format_html('<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{}</pre>',json.dumps(obj.changes,ensure_ascii=False,indent=2))

    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False


from django.contrib.admin.models import LogEntry

@admin.register(LogEntry)
class PreviousAdminLogAdmin(admin.ModelAdmin):
    list_display=('action_time','user','content_type','object_repr','action_flag')
    list_filter=('action_flag','content_type','action_time')
    search_fields=('user__username','object_repr')
    readonly_fields=[field.name for field in LogEntry._meta.fields]
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
