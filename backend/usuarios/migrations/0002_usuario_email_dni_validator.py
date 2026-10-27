import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="email",
            field=models.EmailField(blank=True, max_length=254, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name="usuario",
            name="dni",
            field=models.CharField(
                max_length=8,
                unique=True,
                validators=[django.core.validators.RegexValidator(r"^\d{8}$", "El DNI debe contener exactamente 8 números.")],
            ),
        ),
    ]
