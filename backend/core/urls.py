
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("alumno/", views.inicioalumno, name="alumno"),
    path("profesor/", views.inicioprofe, name="profesor"),
    path("api/actividad/", views.api_actividad, name="api_actividad"),
    path("api/notificaciones/", views.api_notificaciones, name="api_notificaciones"),
]
