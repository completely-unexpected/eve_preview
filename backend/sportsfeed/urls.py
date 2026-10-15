from django.urls import path
from . import views
app_name = "sportsfeed"
urlpatterns = [path('my-slips/', views.my_slips)]
urlpatterns += [path("oddsportal/", views.oddsportal), path("slips/", views.slip_history), path("slips/submit/", views.submit_slip), path("permissions/", views.permissions), path("extra-markets/", views.extra_markets), path("board/", views.board), path("leagues/", views.leagues), path("events/", views.events)]
