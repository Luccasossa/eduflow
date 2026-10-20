from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Proyecto(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proyectos_creados"
    )
    integrantes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="proyectos"
    )
    progreso = models.PositiveSmallIntegerField(
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    fecha_entrega = models.DateField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    def actualizar_progreso(self):
        total = self.tareas.count()
        completadas = self.tareas.filter(estado="completada").count()
        self.progreso = round(completadas * 100 / total) if total else 0
        self.save(update_fields=("progreso", "fecha_actualizacion"))
