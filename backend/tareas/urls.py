
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_tareas, name='lista_tareas'),
    path('api/', views.api_tareas, name='api_tareas'),
    path('api/<int:pk>/', views.api_tarea, name='api_tarea'),
    path('api/<int:pk>/evaluacion/', views.api_calificar_tarea, name='api_calificar_tarea'),
]
