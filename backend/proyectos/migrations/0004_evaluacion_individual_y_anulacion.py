import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("proyectos", "0003_proyecto_profesores_devoluciondocente"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devoluciondocente",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("historica", "Histórica"),
                    ("grupal", "Grupal"),
                    ("individual", "Individual"),
                ],
                default="historica",
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="devoluciondocente",
            name="alumno",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="evaluaciones_individuales",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="devoluciondocente",
            name="anulada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="devoluciondocente",
            name="anulada_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="devoluciones_anuladas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
