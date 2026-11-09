
from django.urls import path
from . import views

app_name = "usuarios"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("registro/", views.registro_view, name="registro"),
    path("logout/", views.logout_view, name="logout"),
    path("api/perfil/", views.api_perfil, name="api_perfil"),
    path("api/cambiar-contrasena/", views.api_cambiar_contrasena, name="api_cambiar_contrasena"),
]
