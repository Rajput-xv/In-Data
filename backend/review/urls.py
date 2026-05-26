from django.urls import path

from . import views

urlpatterns = [
    path("activities/<int:activity_id>/approve/", views.approve, name="activity-approve"),
    path("activities/<int:activity_id>/reject/", views.reject, name="activity-reject"),
]
