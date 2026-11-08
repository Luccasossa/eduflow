import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("archivos", "0003_alter_archivo_archivo"),
        ("tareas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="archivo",
            name="tarea",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="archivos",
                to="tareas.tarea",
            ),
        ),
    ]
