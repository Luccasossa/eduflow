from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tareas", "0002_entrega"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tarea",
            name="retroalimentacion",
            field=models.TextField(blank=True, default=""),
        ),
    ]
