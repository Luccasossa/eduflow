from django.db import models
from django.conf import settings


class Notificacion(models.Model):
    TIPOS = [("comentario", "Comentario"), ("calificacion", "Calificación"), ("general", "General")]
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones"
    )
    mensaje = models.CharField(max_length=255)
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20, choices=TIPOS, default="general")
    tarea = models.ForeignKey("tareas.Tarea", on_delete=models.CASCADE, null=True, blank=True, related_name="notificaciones")

    def __str__(self):
        return self.mensaje


class Actividad(models.Model):
    TIPOS = [("tarea", "Tarea"), ("proyecto", "Proyecto"), ("archivo", "Archivo"), ("adjunto", "Adjunto"), ("comentario", "Comentario"), ("calificacion", "Calificación")]
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="actividades"
    )
    descripcion = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=20, choices=TIPOS, default="tarea")
    tarea = models.ForeignKey("tareas.Tarea", on_delete=models.SET_NULL, null=True, blank=True, related_name="actividades")
    proyecto = models.ForeignKey("proyectos.Proyecto", on_delete=models.SET_NULL, null=True, blank=True, related_name="actividades")
    archivo = models.ForeignKey("archivos.Archivo", on_delete=models.SET_NULL, null=True, blank=True, related_name="actividades")

    def __str__(self):
        return self.descripcion
