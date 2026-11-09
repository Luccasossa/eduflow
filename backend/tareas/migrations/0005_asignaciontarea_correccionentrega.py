import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tareas", "0004_tarea_archivos_adjuntos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AsignacionTarea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_asignacion", models.DateTimeField(auto_now_add=True)),
                ("alumno", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tareas_asignadas", to=settings.AUTH_USER_MODEL)),
                ("profesor", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="asignaciones_tareas_docentes", to=settings.AUTH_USER_MODEL)),
                ("tarea", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="asignaciones", to="tareas.tarea")),
            ],
        ),
        migrations.AddConstraint(model_name="asignaciontarea", constraint=models.UniqueConstraint(fields=("tarea", "alumno"), name="una_asignacion_por_alumno_tarea")),
        migrations.CreateModel(
            name="CorreccionEntrega",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("calificacion", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("comentario", models.TextField(blank=True, default="")),
                ("estado", models.CharField(choices=[("en_revision", "En revisión"), ("corregida", "Corregida"), ("devuelta", "Devuelta para correcciones")], default="corregida", max_length=20)),
                ("fecha_correccion", models.DateTimeField(auto_now_add=True)),
                ("anulada_en", models.DateTimeField(blank=True, null=True)),
                ("anulada_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="correcciones_entregas_anuladas", to=settings.AUTH_USER_MODEL)),
                ("entrega", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="correcciones", to="tareas.entrega")),
                ("profesor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="correcciones_entregas", to=settings.AUTH_USER_MODEL)),
                ("reemplaza", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="versiones_siguientes", to="tareas.correccionentrega")),
            ],
            options={"ordering": ("-fecha_correccion", "-pk")},
        ),
    ]
