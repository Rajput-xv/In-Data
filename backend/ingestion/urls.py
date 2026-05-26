from django.urls import path

from . import views

urlpatterns = [
    path("ingest/<str:source>/", views.ingest_file, name="ingest-file"),
    path("batches/", views.list_batches, name="list-batches"),
    path("batches/<int:batch_id>/", views.batch_detail, name="batch-detail"),
    path("activities/", views.list_activities, name="list-activities"),
    path("activities/<int:activity_id>/", views.activity_detail, name="activity-detail"),
]
