from django.db import models
from django.conf import settings


class Tarea(models.Model):
    PRIORIDADES = [
        ("alta", "Alta"),
        ("media", "Media"),
        ("baja", "Baja"),
    ]

    ESTADOS = [
        ("pendiente", "Por hacer"),
        ("en_progreso", "En progreso"),
        ("completada", "Completada"),
    ]

    titulo = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDADES,
        default="media"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente"
    )
    fecha_vencimiento = models.DateField(blank=True, null=True)
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tareas_creadas"
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tareas"
    )
    calificacion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    retroalimentacion = models.TextField(blank=True)

    evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas_evaluadas"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo