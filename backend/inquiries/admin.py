from django.contrib import admin
from django.utils import timezone
from .models import Inquiry

@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display = ["title", "member", "status", "created_at", "answered_at"]
    list_filter = ["answered_at"]
    search_fields = ["title", "body", "member__username", "member__nickname"]
    readonly_fields = ["member", "title", "body", "answered_by", "answered_at", "created_at", "updated_at"]
    fields = ["member", "title", "body", "answer", "answered_by", "answered_at", "created_at", "updated_at"]
    @admin.display(description="처리 상태")
    def status(self, obj):
        return "답변 완료" if obj.answer else "답변 대기"
    def has_add_permission(self, request):
        return False
    def save_model(self, request, obj, form, change):
        if "answer" in form.changed_data:
            obj.answer = obj.answer.strip()
            obj.answered_by = request.user if obj.answer else None
            obj.answered_at = timezone.now() if obj.answer else None
        super().save_model(request, obj, form, change)
