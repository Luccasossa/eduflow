import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import archivos.storage
import archivos.validators
import tareas.models


class Migration(migrations.Migration):
    dependencies = [
        ("archivos", "0004_archivo_tarea"),
        ("tareas", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Entrega",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("archivo", models.FileField(storage=archivos.storage.PrivateFileSystemStorage(), upload_to=tareas.models.ruta_entrega, validators=[archivos.validators.validar_archivo])),
                ("fecha_entrega", models.DateTimeField(auto_now_add=True)),
                ("estado", models.CharField(choices=[("entregada", "Entregada"), ("en_revision", "En revisión"), ("aprobada", "Aprobada"), ("rechazada", "Requiere corrección")], default="entregada", max_length=20)),
                ("observaciones", models.TextField(blank=True, default="")),
                ("alumno", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entregas_tareas", to=settings.AUTH_USER_MODEL)),
                ("tarea", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entregas", to="tareas.tarea")),
            ],
            options={"ordering": ["-fecha_entrega"]},
        ),
        migrations.AddConstraint(
            model_name="entrega",
            constraint=models.UniqueConstraint(fields=("tarea", "alumno"), name="una_entrega_por_alumno_tarea"),
        ),
    ]
