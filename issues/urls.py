from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Public & Resident
    path('', views.home, name='home'),
    path('report/', views.report_issue, name='report_issue'),
    path('my-reports/', views.my_reports, name='my_reports'),
    path('track/<str:tracking_code>/', views.track_detail, name='track_detail'),

    # Administrator Civic Action Center
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('issues/<int:pk>/', views.issue_detail, name='issue_detail'),

    # AJAX / APIs
    path('api/analyze/', views.api_analyze_preview, name='api_analyze_preview'),
    path('api/map-issues/', views.api_map_issues, name='api_map_issues'),
    path('api/extract-photo-gps/', views.api_extract_photo_gps, name='api_extract_photo_gps'),

    # Auth
    path('login/', views.user_login, name='login'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
]
