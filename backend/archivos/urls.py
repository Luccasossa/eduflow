from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_archivos, name='lista_archivos'),
    path('subir/', views.subir_archivo, name='subir_archivo'),
]
