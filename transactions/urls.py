from django.urls import path
from django.urls import path
from . import api_views, web_views,views
# transactions/urls.py

# WEB URLS
urlpatterns = [
    path("dashboard/", web_views.dashboard_view, name="dashboard"),
    path("dashboard/provider/<str:provider>/", web_views.provider_transactions_view, name="provider_transactions"),
    path("", views.index, name="index"),
    path("upload/", views.sms_upload_form, name="sms_upload_form"),
    path("all/transactions/", web_views.all_transactions_view, name="list_transactions"),
    path("dashboard/transactions/", web_views.all_transactions_view, name="all_transactions"),
]
# APIS URLS
urlpatterns += [
    # path('api/providers/', api_views.ProviderListAPIView.as_view(), name='provider-list'),
    path('api/parse-sms/', api_views.parse_and_store_sms, name='parse-sms'),
    path('api/transactions/', api_views.list_transactions, name='list-transactions'),
    path('api/transactions/<str:provider>/', api_views.provider_transactions_api, name='provider-transactions'),
    path('api/dashboard-summary/', api_views.dashboard_summary_view, name='dashboard-summary'),
    path('api/active-providers/', api_views.providers_with_transactions, name='active-providers'),
    path('api/providers/', api_views.providers_view, name='providers'),
    path('api/report/', api_views.generate_pdf_report, name='report'),
    path('api/filters/', api_views.filters_view, name='filters'),
    path('api/charts-summary/', api_views.charts_summary_view, name='charts-summary'),
]

# PDF DOWNLOAD
urlpatterns += [
    path("dashboard/report/", views.generate_pdf_report, name="generate_pdf_report"),
]

from .views import register_user
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns += [
    path('api/register/', register_user, name='register'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]


