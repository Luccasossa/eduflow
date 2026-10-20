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
    profesores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="proyectos_supervisados",
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


class DevolucionDocente(models.Model):
    """Entrada inmutable de evaluación o retroalimentación asociada al proyecto."""
    proyecto = models.ForeignKey(Proyecto, on_delete=models.PROTECT, related_name="devoluciones")
    tarea = models.ForeignKey("tareas.Tarea", on_delete=models.SET_NULL, null=True, blank=True, related_name="devoluciones")
    documento = models.ForeignKey("documentos.Documento", on_delete=models.SET_NULL, null=True, blank=True, related_name="devoluciones")
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="devoluciones_docentes")
    comentario = models.TextField(blank=True)
    calificacion = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-fecha_creacion", "-pk")

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.tarea_id and self.documento_id:
            raise ValidationError("La devolución solo puede vincularse a una tarea o a un documento.")
        if self.tarea_id and self.tarea.proyecto_id != self.proyecto_id:
            raise ValidationError({"tarea": "La tarea debe pertenecer al proyecto indicado."})
        if self.documento_id and self.documento.proyecto_id != self.proyecto_id:
            raise ValidationError({"documento": "El documento debe pertenecer al proyecto indicado."})
        if not self.comentario.strip() and self.calificacion is None:
            raise ValidationError("La devolución debe incluir un comentario o una calificación.")

    def __str__(self):
        return f"Devolución de {self.autor} para {self.proyecto}"
