
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# VALIDACIÓN DE ARCHIVOS

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
}


def validar_archivo(archivo):
    if not archivo:
        raise ValidationError(
            "Debés seleccionar un archivo."
        )

    extension = Path(archivo.name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Formato no permitido. "
            "Subí PDF, Word, Excel, PowerPoint o una imagen."
        )

    if archivo.size > MAX_FILE_SIZE:
        raise ValidationError(
            "El archivo no puede superar los 10 MB."
        )

    if archivo.size == 0:
        raise ValidationError(
            "El archivo está vacío."
        )


# MODELO DE TAREAS EXISTENTE

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
        default="media",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente",
    )

    fecha_vencimiento = models.DateField(
        blank=True,
        null=True,
    )

    creador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tareas_creadas",
    )

    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tareas",
    )

    calificacion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    retroalimentacion = models.TextField(
        blank=True,
        default="",
    )

    evaluado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tareas_evaluadas",
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.titulo


# MODELO NUEVO: ENTREGAS DE LOS ALUMNOS

def ruta_entrega(instance, filename):
    return (
        f"entregas/tarea_{instance.tarea_id}/"
        f"alumno_{instance.alumno_id}/{filename}"
    )


class Entrega(models.Model):

    ESTADOS = [
        ("entregada", "Entregada"),
        ("en_revision", "En revisión"),
        ("aprobada", "Aprobada"),
        ("rechazada", "Requiere corrección"),
    ]

    tarea = models.ForeignKey(
        Tarea,
        on_delete=models.CASCADE,
        related_name="entregas",
    )

    alumno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entregas_tareas",
    )

    archivo = models.FileField(
        upload_to=ruta_entrega,
        validators=[validar_archivo],
    )

    fecha_entrega = models.DateTimeField(
        auto_now_add=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="entregada",
    )

    observaciones = models.TextField(
        blank=True,
        default="",
    )

    class Meta:
        ordering = ["-fecha_entrega"]
        constraints = [
            models.UniqueConstraint(
                fields=["tarea", "alumno"],
                name="una_entrega_por_alumno_tarea",
            )
        ]

    def __str__(self):
        return (
            f"Entrega de {self.alumno} "
            f"para {self.tarea}"
        )
