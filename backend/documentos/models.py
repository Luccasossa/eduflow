from django.db import models
from django.conf import settings


class Documento(models.Model):
    titulo = models.CharField(max_length=200)
    contenido = models.TextField(blank=True)
    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documentos_creados"
    )
    colaboradores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="documentos_compartidos"
    )
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.CASCADE,
        related_name="documentos",
        null=True,
        blank=True
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
        related_name="documentos_evaluados"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo