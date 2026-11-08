from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_proyectos, name='lista_proyectos'),
    path('api/alumnos/', views.api_alumnos, name='api_alumnos'),
    path('api/', views.api_proyectos, name='api_proyectos'),
    path('api/<int:pk>/', views.api_proyecto, name='api_proyecto'),
    path('api/<int:pk>/devoluciones/', views.api_devoluciones, name='api_devoluciones'),
    path('api/devoluciones/<int:pk>/', views.api_devolucion, name='api_devolucion'),
    path('api/<int:pk>/archivos/', views.api_archivos_proyecto, name='api_archivos_proyecto'),
]
