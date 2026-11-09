
from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_documentos, name='lista_documentos'),
    path('api/', views.api_documentos, name='api_documentos'),
    path('api/<int:pk>/', views.api_documento, name='api_documento'),
    path('api/<int:pk>/evaluacion/', views.api_evaluar_documento, name='api_evaluar_documento'),
    path('api/<int:pk>/estado-revision/', views.api_estado_revision_documento, name='api_estado_revision_documento'),
]
