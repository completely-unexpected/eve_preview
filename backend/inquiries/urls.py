from django.urls import path
from . import views
app_name = "inquiries"
urlpatterns = [path("<int:pk>/read/", views.read_answer, name="read_answer"), path("", views.listing, name="list"), path("<int:pk>/", views.detail, name="detail")]
