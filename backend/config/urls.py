from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.static import serve


def frontend_asset(request, path, document_root):
    if not settings.DEBUG:
        raise Http404
    return serve(request, path, document_root=document_root)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/inquiries/", include("inquiries.urls")),
    path("api/notices/", include("notices.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]

# Local development only. A production deployment must serve static assets separately.
for asset in ("styles.css", "functionality.css", "auth.css", "app.js", "auth.js", "inquiries.js"):
    urlpatterns.append(path(asset, frontend_asset, {"path": asset, "document_root": settings.FRONTEND_DIR}))
urlpatterns.append(path("assets/<path:path>", frontend_asset, {"document_root": settings.FRONTEND_DIR / "assets"}))
