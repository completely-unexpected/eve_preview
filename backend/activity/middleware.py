from uuid import uuid4
from time import monotonic
from .tracking import context, record


class ActivityMiddleware:
    def __init__(self,get_response): self.get_response=get_response

    def __call__(self,request):
        if not (request.path.startswith('/api/') or request.path.startswith('/admin/') or request.path.startswith('/partner-admin/')):
            return self.get_response(request)
        def actor():
            if request.user.is_authenticated:
                return request.user.username, 'admin' if request.user.is_staff else 'member'
            from accounts.partner_admin import current_partner
            partner=current_partner(request)
            return (partner.username,'partner') if partner else ('비로그인','anonymous')
        name,kind=actor()
        values={'request_id':uuid4(),'actor':name,'actor_kind':kind,'path':request.path[:500],'method':request.method}
        token=context.set(values);start=monotonic()
        try:
            response=self.get_response(request)
            # A successful login can establish the identity during this request.
            if kind=='anonymous':
                name,kind=actor();values.update(actor=name,actor_kind=kind)
            if kind in ('member','admin','partner'):
                from .pages import capture_ip
                capture_ip(name,kind,request.META.get('REMOTE_ADDR'))
            if request.method=='GET' and response.status_code==200 and (request.path.startswith('/admin/') or request.path.startswith('/partner-admin/')):
                from .pages import touch
                touch(name,kind,request.path,request.META.get('REMOTE_ADDR'))
            details={'duration_ms':round((monotonic()-start)*1000)}
            for key in ('action','status','source','mode','amount','event_id','page'):
                value=request.POST.get(key) if request.method=='POST' else request.GET.get(key)
                if value is not None: details[key]=str(value)[:100]
            if request.path.endswith('/login/') and request.method=='POST' and kind=='anonymous':
                details['attempted_username']=request.POST.get('username','')[:150]
            record('request',changes=details,status=response.status_code)
            return response
        finally:
            context.reset(token)
