from django.contrib import admin
from django.urls import path, include
from .import views

app_name = "dashboard"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("swot/", views.swot, name="swot"),
    path('feasibility/', views.feasibility, name='feasibility'),
    path('risk/', views.risk, name='risk'),
    path("history/", views.history, name="history"),
    path('delete/<int:id>/', views.delete_submission, name='delete'),
    path("guide/", views.guide, name="guide"),
    path('update/<int:id>/', views.update_message, name='update'),
    path('monetization/', views.monetization, name='monetization'),
    path('download/', views.download_report, name='download_report'),
    path("profile/", views.profile_view, name="profile"),
    path('edit_profile/', views.edit_profile, name='edit_profile'),
    path('testimonials/', views.testimonials_view, name='testimonials'),
]
