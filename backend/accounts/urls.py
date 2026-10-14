from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("session/", views.session, name="session"),
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
]
