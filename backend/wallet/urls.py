from django.urls import path
from . import views
app_name="wallet"
urlpatterns=[path("",views.overview,name="overview"),path("apply/",views.apply,name="apply"),path("convert/",views.convert,name="convert"),path("account-request/",views.account_request,name="account_request")]
