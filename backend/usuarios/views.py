from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_POST

from .forms import RegistroUsuarioForm
from .models import PerfilUsuario


def login_view(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")

    if request.method == "POST":
        dni = request.POST.get("dni", "").strip()
        password = request.POST.get("password", "")
        if not dni or not password:
            messages.error(request, "Completa el DNI y la contraseña.")
        else:
            usuario = authenticate(request, dni=dni, password=password)
            if usuario is None:
                messages.error(request, "El DNI o la contraseña son incorrectos.")
            else:
                login(request, usuario)
                request.session.set_expiry(None if request.POST.get("remember") else 0)
                return redirect("core:inicio")

    return render(request, "inicio_sesion.html")


def registro_view(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")

    form = RegistroUsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                usuario = form.save()
                # El registro público siempre crea alumnos. El rol enviado por el cliente se ignora.
                PerfilUsuario.objects.create(usuario=usuario, rol="alumno")
        except IntegrityError:
            form.add_error("dni", "El DNI o el correo ya están registrados.")
        else:
            messages.success(request, "Tu cuenta se creó correctamente. Ya puedes iniciar sesión.")
            return redirect("usuarios:login")

    return render(request, "registro.html", {"form": form})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Cerraste sesión correctamente.")
    return redirect("usuarios:login")
