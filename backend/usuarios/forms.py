from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from .models import Usuario


class RegistroUsuarioForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    confirm_password = forms.CharField(
        label="Confirmar contrase\u00f1a",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "dni")
        labels = {
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "dni": "DNI",
        }

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        if not dni.isascii() or not dni.isdigit() or len(dni) != 8:
            raise ValidationError("El DNI debe contener exactamente 8 números.")
        if Usuario.objects.filter(dni=dni).exists():
            raise ValidationError("Ya existe una cuenta registrada con ese DNI.")
        return dni

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta registrada con ese correo.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirmation = cleaned.get("confirm_password")
        if password and confirmation and password != confirmation:
            self.add_error("confirm_password", "Las contrase\u00f1as no coinciden.")
        return cleaned

    def clean_password(self):
        password = self.cleaned_data["password"]
        usuario = Usuario(
            dni=self.cleaned_data.get("dni", ""),
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
            email=self.cleaned_data.get("email", ""),
        )
        password_validation.validate_password(password, user=usuario)
        return password

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.email = self.cleaned_data["email"]
        usuario.set_password(self.cleaned_data["password"])
        if commit:
            usuario.save()
        return usuario
