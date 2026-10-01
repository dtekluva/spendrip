from django.urls import path

from . import views

urlpatterns = [
    path("health", views.Health.as_view()),
    path("summary", views.Summary.as_view()),
    path("plans", views.Plans.as_view()),
    path("activity", views.Activity.as_view()),
    path("dev/top-up", views.DevTopUp.as_view()),
    path("dev/tick", views.DevTick.as_view()),
]
