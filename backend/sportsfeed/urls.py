from django.urls import path
from . import views
app_name = "sportsfeed"
urlpatterns = [path("permissions/", views.permissions), path("extra-markets/", views.extra_markets), path("board/", views.board), path("leagues/", views.leagues), path("events/", views.events)]
