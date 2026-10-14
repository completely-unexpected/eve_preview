from django.conf import settings
from django.db import models

class Inquiry(models.Model):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="회원", on_delete=models.CASCADE)
    title = models.CharField("제목", max_length=200)
    body = models.TextField("문의 내용", max_length=10000)
    answer = models.TextField("답변", blank=True, max_length=10000)
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="답변 관리자", on_delete=models.SET_NULL, null=True, blank=True, related_name="answered_inquiries")
    answered_at = models.DateTimeField("답변일", null=True, blank=True)
    answer_read_at = models.DateTimeField("답변 확인일", null=True, blank=True, editable=False)
    created_at = models.DateTimeField("문의일", auto_now_add=True)
    updated_at = models.DateTimeField("수정일", auto_now=True)
    class Meta:
        verbose_name = "1:1 문의"
        verbose_name_plural = "1:1 문의"
        ordering = ["-created_at", "-pk"]
    def __str__(self):
        return self.title
