import os
import uuid

from django.db import models
from django.conf import settings
from .storage import PrivateFileSystemStorage

class Carpeta(models.Model):
    nombre = models.CharField(max_length=150)

    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carpetas"
    )

    carpeta_padre = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcarpetas"
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre


def ruta_archivo_segura(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    return f"archivos/{instance.propietario_id}/{uuid.uuid4().hex}{extension}"


class Archivo(models.Model):
    archivo = models.FileField(upload_to=ruta_archivo_segura, storage=PrivateFileSystemStorage())
    nombre_original = models.CharField(max_length=255, default="")
    tipo = models.CharField(max_length=100, default="application/octet-stream")
    tamano = models.PositiveBigIntegerField(default=0)

    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archivos"
    )

    carpeta = models.ForeignKey(
        Carpeta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos"
    )

    # NUEVO: relación opcional con un proyecto
    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos"
    )

    fecha_subida = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.archivo.name
