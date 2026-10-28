from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_archivos, name='lista_archivos'),
    path('subir/', views.subir_archivo, name='subir_archivo'),
    path('api/', views.api_archivos, name='api_archivos'),
    path('api/carpetas/', views.api_carpetas, name='api_carpetas'),
    path('api/<int:pk>/descargar/', views.descargar_archivo, name='descargar_archivo'),
]
