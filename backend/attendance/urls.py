from django.urls import path
from . import views
app_name = "attendance"
urlpatterns = [path("", views.overview, name="overview"), path("check/", views.check, name="check")]
