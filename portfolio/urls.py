from django.urls import path
from . import views
from . import auth_views

urlpatterns = [
    path("login/",auth_views.LoginView.as_view(template_name="portfolio/login.html"), name="login",),
    path("logout/",auth_views.LogoutView.as_view(),name="logout",),
    path("", views.dashboard, name="dashboard"),
    path("reports/", views.reports, name="reports"),
    path("api/dashboard/", views.dashboard_api, name="dashboard_api"),
    path("api/investments/", views.investment_api, name="investment_api"),
    path("api/monthly/", views.monthly_api, name="monthly_api"),
    path("api/targets/", views.targets_api, name="targets_api"),
    path("api/goals/", views.goal_api, name="goal_api"),
    path("api/report/", views.report_api, name="report_api"),
]
