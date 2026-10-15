from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("partner/members/", views.partner_members, name="partner_members"),
    path("profile/", views.profile, name="profile"),
    path("details/", views.details, name="details"),
    path("session/", views.session, name="session"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("password-change/", views.password_change, name="password_change"),
    path("logout/", views.logout, name="logout"),
]
