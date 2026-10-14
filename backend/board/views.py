from django import forms
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from math import ceil
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods
from notices.models import Notice
from .models import Post
class PostForm(forms.Form):
    title=forms.CharField(label="제목",max_length=200)
    body=forms.CharField(label="내용",max_length=10000)
def data(post):
    return {"id":post.pk,"title":post.title,"author":post.author.nickname or "회원" if post.author else "탈퇴 회원","createdAt":post.created_at.isoformat()}
@never_cache
@require_http_methods(["GET","POST"])
@csrf_protect
def listing(request):
    if request.method=="POST":
        if not request.user.is_authenticated:
            return JsonResponse({"ok":False,"message":"로그인 후 글을 작성해 주세요."},status=401)
        form=PostForm(request.POST)
        if not form.is_valid():return JsonResponse({"ok":False,"errors":form.errors.get_json_data()},status=400)
        now=timezone.now()
        # Reserve the posting slot atomically, including across tabs and sessions.
        with transaction.atomic():
            allowed=get_user_model().objects.filter(pk=request.user.pk,is_active=True).filter(Q(board_last_post_at__isnull=True)|Q(board_last_post_at__lte=now-timedelta(seconds=30))).update(board_last_post_at=now)
            if not allowed:
                last=get_user_model().objects.values_list("board_last_post_at",flat=True).get(pk=request.user.pk)
                seconds=max(1,ceil((last+timedelta(seconds=30)-now).total_seconds())) if last else 30
                response=JsonResponse({"ok":False,"message":f"연속 등록을 제한하고 있습니다. {seconds}초 후 다시 등록해 주세요.","retryAfter":seconds},status=429)
                response["Retry-After"]=str(seconds)
                return response
            post=Post.objects.create(author=request.user,**form.cleaned_data)
        return JsonResponse({"ok":True,"post":data(post)},status=201)
    query=request.GET.get("q", "").strip()[:200]
    posts=Post.objects.filter(is_published=True).select_related("author")
    if query:posts=posts.filter(Q(title__icontains=query)|Q(body__icontains=query))
    page=Paginator(posts,20).get_page(request.GET.get("page"))
    pinned=[{"id":n.pk,"title":n.title} for n in Notice.objects.filter(is_published=True,is_pinned=True)]
    return JsonResponse({"ok":True,"pinnedNotices":pinned,"items":[data(p) for p in page],"page":page.number,"pages":page.paginator.num_pages,"count":page.paginator.count,"query":query})
@never_cache
@require_GET
def detail(request,pk):
    post=get_object_or_404(Post.objects.select_related("author"),pk=pk,is_published=True)
    return JsonResponse({"ok":True,"post":{**data(post),"body":post.body}})
