from django import forms
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
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
