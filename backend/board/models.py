from django.conf import settings
from django.db import models
class Post(models.Model):
    author=models.ForeignKey(settings.AUTH_USER_MODEL,verbose_name="작성 회원",on_delete=models.SET_NULL,null=True)
    title=models.CharField("제목",max_length=200)
    body=models.TextField("내용",max_length=10000)
    is_published=models.BooleanField("게시",default=True)
    created_at=models.DateTimeField("작성일",auto_now_add=True)
    class Meta:
        verbose_name="게시글"
        verbose_name_plural="게시글"
        ordering=["-created_at","-pk"]
    def __str__(self):return self.title
