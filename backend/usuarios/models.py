from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UsuarioManager(BaseUserManager):
    def create_user(self, dni, password=None, **extra_fields):
        if not dni:
            raise ValueError("El DNI es obligatorio")

        usuario = self.model(dni=dni, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, dni, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(dni, password, **extra_fields)


class Usuario(AbstractUser):
    username = None
    email = None

    dni = models.CharField(max_length=8, unique=True)

    USERNAME_FIELD = "dni"
    REQUIRED_FIELDS = []

    objects = UsuarioManager()

    def __str__(self):
        return self.dni


class PerfilUsuario(models.Model):
    ROLES = [
        ("alumno", "Alumno"),
        ("profesor", "Profesor"),
    ]

    usuario = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="perfil"
    )

    rol = models.CharField(
        max_length=20,
        choices=ROLES,
        default="alumno"
    )

    foto = models.ImageField(
        upload_to="perfiles/",
        blank=True,
        null=True
    )

    def __str__(self):
        return f"{self.usuario.dni} - {self.rol}"