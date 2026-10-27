from django import forms
from django.contrib import admin

from usuarios.models import Usuario
from .models import DevolucionDocente, Proyecto


class ProyectoAdminForm(forms.ModelForm):
    profesores = forms.ModelMultipleChoiceField(
        queryset=Usuario.objects.filter(perfil__rol="profesor", is_active=True),
        required=False,
        help_text="Solo docentes con cuenta activa pueden supervisar este proyecto.",
    )

    class Meta:
        model = Proyecto
        fields = "__all__"


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    form = ProyectoAdminForm
    list_display = ("nombre", "creador", "fecha_entrega")
    filter_horizontal = ("integrantes", "profesores")


@admin.register(DevolucionDocente)
class DevolucionDocenteAdmin(admin.ModelAdmin):
    list_display = ("proyecto", "autor", "calificacion", "fecha_creacion")
    readonly_fields = ("proyecto", "tarea", "documento", "autor", "comentario", "calificacion", "fecha_creacion")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
