from datetime import timedelta
from django import forms
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404,redirect
from django.template.response import TemplateResponse
from django.contrib import messages
from django.utils import timezone
from .models import Wallet
from accounts.models import User
from activity.models import PagePresence
from activity.pages import page_name


class MemberDetailForm(forms.ModelForm):
    class Meta:
        model=User
        fields=('legal_name','phone_number','wallet_number','admin_notes')
        widgets={'admin_notes':forms.Textarea(attrs={'rows':5,'cols':65})}


def detail(model_admin,request,object_id):
    if request.method not in ('GET','POST'): return HttpResponseNotAllowed(['GET','POST'])
    if not model_admin.has_view_permission(request) or not request.user.has_perm('accounts.view_user'): raise PermissionDenied
    wallet=get_object_or_404(Wallet.objects.select_related('member'),pk=object_id)
    user=wallet.member
    can_edit=request.user.has_perm('accounts.change_user')
    form=MemberDetailForm(request.POST if request.method=='POST' else None,instance=user,initial={'legal_name':user.legal_name or user.get_full_name()})
    if request.method=='POST':
        if not can_edit: raise PermissionDenied
        if form.is_valid():
            changed=form.save(commit=False)
            changed.save(update_fields=form.Meta.fields)
            messages.success(request,'회원 정보를 저장했습니다.')
            return redirect(request.path)
    if not can_edit:
        for field in form.fields.values(): field.disabled=True
    presence=PagePresence.objects.filter(actor=user.username,actor_kind__in=['member','admin']).order_by('-last_seen').first()
    location=page_name(presence.route) if presence else '확인된 이용 기록 없음'
    if presence and presence.last_seen<timezone.now()-timedelta(seconds=90): location+=' (최근 위치 · 현재 활동 확인 안 됨)'
    return TemplateResponse(request,'admin/wallet/member_detail.html',{**model_admin.admin_site.each_context(request),'title':f'{user.username} · 회원 상세 정보','member':user,'form':form,'can_edit':can_edit,'location':location,'presence':presence})
