"""Project URL routing. Apps own their own sub-routers."""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("api/", include("ingestion.urls")),
    path("api/", include("review.urls")),
]
