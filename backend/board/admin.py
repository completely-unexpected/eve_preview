from django.contrib import admin
from .models import Post
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display=["title","author","is_published","created_at"]
    list_filter=["is_published"]
    search_fields=["title","body","author__nickname"]
    readonly_fields=["author","created_at"]
    def has_add_permission(self,request):return False
