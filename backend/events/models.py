from django.db import models
class Event(models.Model):
    title = models.CharField("제목", max_length=200)
    tag = models.CharField("배너 문구", max_length=50, blank=True)
    summary = models.CharField("요약", max_length=300)
    body = models.TextField("내용", max_length=10000)
    symbol = models.CharField("표시 아이콘", max_length=8, default="🎁")
    is_published = models.BooleanField("게시", default=False)
    sort_order = models.PositiveIntegerField("표시 순서", default=0)
    class Meta:
        verbose_name = "이벤트"
        verbose_name_plural = "이벤트"
        ordering = ["sort_order", "pk"]
    def __str__(self):
        return self.title
