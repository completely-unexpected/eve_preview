PAGES={'home':'홈','sports':'스포츠 · 프리매치','inplay':'스포츠 · 인플레이','esports':'E스포츠','casino':'카지노','games':'게임 목록','events':'이벤트','inquiries':'1:1 문의','account':'회원정보','partner':'하위 협력사','oddsportal':'OddsPortal 경기·결과','board':'게시판','wallet':'입금·출금','attendance':'출석체크','notices':'공지사항','betting-history':'배팅 내역'}


def page_name(route):
    if route.startswith('/partner-admin'): return '하위 협력사 관리자'
    if route.startswith('/admin/'):
        if route.startswith('/admin/betting-status/'): return '관리자 · 배팅현황'
        if route.startswith('/admin/overview/'): return '관리자 · 현황'
        parts=route.strip('/').split('/')
        if len(parts)>=3:
            from django.apps import apps
            try: return '관리자 · '+str(apps.get_model(parts[1],parts[2])._meta.verbose_name_plural)
            except LookupError: pass
        return '관리자'
    parts=route.removeprefix('#/').split('/')
    label=PAGES.get(parts[0],'기타 화면')
    if len(parts)>1:
        if parts[0]=='wallet': return {'convert':'포인트 전환','deposit':'입금 신청','withdraw':'출금 신청'}.get(parts[1],label)
        if parts[0] in ('notices','board','inquiries','games','events'): label+=' · 상세'
    return label


def touch(actor,kind,route,ip=None):
    from django.utils import timezone
    from .models import PagePresence
    if kind not in ('member','admin','partner'): return
    defaults={'route':route[:500],'last_seen':timezone.now()}
    if ip:
        from ipaddress import ip_address
        try: defaults['last_ip']=str(ip_address(ip))
        except ValueError: pass
    PagePresence.objects.update_or_create(actor=actor,actor_kind=kind,defaults=defaults)


def capture_ip(actor,kind,ip):
    from ipaddress import ip_address
    from .models import PagePresence
    try: address=str(ip_address(ip or ''))
    except ValueError: return
    PagePresence.objects.filter(actor=actor,actor_kind=kind).exclude(last_ip=address).update(last_ip=address)
