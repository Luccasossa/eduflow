from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render


def requiere_rol(rol):
    def decorador(vista):
        @wraps(vista)
        @login_required
        def protegida(request, *args, **kwargs):
            perfil = getattr(request.user, "perfil", None)
            if perfil is None or perfil.rol != rol:
                return HttpResponseForbidden("No tienes permisos para acceder a esta sección.")
            return vista(request, *args, **kwargs)

        return protegida

    return decorador


@login_required
def inicio(request):
    perfil = getattr(request.user, "perfil", None)
    if perfil is None:
        return HttpResponseForbidden("Tu cuenta no tiene un rol asignado. Contacta al administrador.")
    return redirect("core:profesor" if perfil.rol == "profesor" else "core:alumno")


@requiere_rol("alumno")
def inicioalumno(request):
    return render(request, "index.html")


@requiere_rol("profesor")
def inicioprofe(request):
    return render(request, "eduflow-todo-en-uno (1).html")
