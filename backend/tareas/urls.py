
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_tareas, name='lista_tareas'),
    path('api/', views.api_tareas, name='api_tareas'),
    path('api/asignaciones/', views.api_asignaciones, name='api_asignaciones'),
    path('api/alumnos-asignables/', views.api_alumnos_asignables, name='api_alumnos_asignables'),
    path('api/<int:pk>/', views.api_tarea, name='api_tarea'),
    path('api/<int:pk>/evaluacion/', views.api_calificar_tarea, name='api_calificar_tarea'),
    path('api/<int:pk>/evaluaciones/', views.api_evaluaciones, name='api_evaluaciones'),
    path('api/<int:pk>/evaluaciones/grupal/', views.api_evaluacion_grupal, name='api_evaluacion_grupal'),
    path('api/<int:pk>/evaluaciones/individual/<int:alumno_id>/', views.api_evaluacion_individual, name='api_evaluacion_individual'),
    path('api/<int:pk>/entregas/', views.api_entregas, name='api_entregas'),
    path('api/<int:pk>/entregas/<int:entrega_id>/revision/', views.api_revision_entrega, name='api_revision_entrega'),
    path('api/<int:pk>/archivos/', views.api_archivos_tarea, name='api_archivos_tarea'),
    path('entregas/<int:pk>/descargar/', views.descargar_entrega, name='descargar_entrega'),
    path('entregas/<int:pk>/correccion/', views.api_correccion_entrega, name='api_correccion_entrega'),
]
