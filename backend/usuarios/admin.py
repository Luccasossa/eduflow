from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import PerfilUsuario, Usuario


class EduflowUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("dni",)


class EduflowUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    can_delete = False
    extra = 1

    def get_readonly_fields(self, request, obj=None):
        if obj and hasattr(obj, "perfil") and obj.perfil.especialidad:
            return ("especialidad",)
        return super().get_readonly_fields(request, obj)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    add_form = EduflowUserCreationForm
    form = EduflowUserChangeForm
    model = Usuario
    inlines = (PerfilUsuarioInline,)
    ordering = ("dni",)
    list_display = ("dni", "first_name", "last_name", "email", "is_staff", "is_active")
    search_fields = ("dni", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("dni", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "email")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("dni", "password1", "password2")}),
    )
    readonly_fields = ("last_login", "date_joined")
    filter_horizontal = ("groups", "user_permissions")
