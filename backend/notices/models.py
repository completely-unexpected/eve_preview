from django.db import models

class Notice(models.Model):
    title = models.CharField("제목", max_length=200)
    body = models.TextField("내용")
    is_published = models.BooleanField("게시", default=False)
    is_pinned = models.BooleanField("상단 고정", default=False)
    created_at = models.DateTimeField("작성일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)

    class Meta:
        verbose_name = "공지사항"
        verbose_name_plural = "공지사항"
        ordering = ["-is_pinned", "-created_at", "-pk"]

    def __str__(self):
        return self.title
