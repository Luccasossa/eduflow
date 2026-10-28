from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    name = 'usuarios'
    # The users.0002 migration explicitly converts both user PKs to AutoField.
    # Keep the live models aligned with that established schema without
    # generating another PK migration.
    default_auto_field = 'django.db.models.AutoField'
