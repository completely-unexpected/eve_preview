from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path
from django.views.generic import TemplateView
from django.views.static import serve
from .dashboard import overview
from accounts import partner_admin
from activity.views import navigation
from .betting_status import betting_status, summary


def frontend_asset(request, path, document_root):
    if not settings.DEBUG:
        raise Http404
    return serve(request, path, document_root=document_root)

urlpatterns = [
    path('api/activity/navigation/', navigation),
    path('admin/summary/', admin.site.admin_view(summary), name='admin_summary'),
    path('admin/betting-status/', admin.site.admin_view(betting_status), name='admin_betting_status'),
    path("partner-admin/", partner_admin.dashboard, name="partner_admin"),
    path("partner-admin/login/", partner_admin.login, name="partner_admin_login"),
    path("partner-admin/logout/", partner_admin.logout, name="partner_admin_logout"),
    path("admin/overview/", admin.site.admin_view(overview), name="admin_overview"),
    path("admin/", admin.site.urls),
    path("api/inquiries/", include("inquiries.urls")),
    path("api/games/", include("catalog.urls")),
    path("api/events/", include("events.urls")),
    path("api/wallet/", include("wallet.urls")),
    path("api/sports/", include("sportsfeed.urls")),
    path("api/attendance/", include("attendance.urls")),
    path("api/board/", include("board.urls")),
    path("api/notices/", include("notices.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="home"),
]

# Local development only. A production deployment must serve static assets separately.
for asset in ("styles.css", "functionality.css", "auth.css", "app.js", "auth.js", "inquiries.js", "board.js", "wallet.js", "account.js", "attendance.js", "sports.js", "cart.js", "powerball.js", "partner.js", "oddsportal.js", "betting-history.js", "activity.js"):
    urlpatterns.append(path(asset, frontend_asset, {"path": asset, "document_root": settings.FRONTEND_DIR}))
urlpatterns.append(path("assets/<path:path>", frontend_asset, {"document_root": settings.FRONTEND_DIR / "assets"}))
