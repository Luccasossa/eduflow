
from django.urls import path
from django.shortcuts import redirect

from . import views

app_name = "core"

urlpatterns = [
    path("", lambda request: redirect("usuarios:login"), name="inicio"),
    path("alumno/", views.inicioalumno, name="alumno"),
    path("profesor/", views.inicioprofe, name="profesor"),
]
