from django.urls import path
from . import views
from sportsfeed import powerball, views as slip_views
app_name="catalog"
urlpatterns=[path("powerball/board/", powerball.board), path("powerball/slips/", slip_views.slip_history, {"source":"powerball"}), path("powerball/submit/", slip_views.submit_slip, {"source":"powerball"}), path("",views.listing,name="list"),path("<slug:slug>/",views.detail,name="detail")]
