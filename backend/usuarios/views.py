import logging

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
from django.shortcuts import redirect, render
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_POST

from .forms import RegistroUsuarioForm
from .models import PerfilUsuario


def _json_body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


@login_required
@require_http_methods(["GET", "PATCH"])
def api_perfil(request):
    perfil = PerfilUsuario.objects.filter(usuario=request.user).first()
    if perfil is None:
        return JsonResponse({"error": "La cuenta no tiene un perfil asignado."}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "perfil": {
                "nombres": request.user.first_name,
                "apellidos": request.user.last_name,
                "correo": request.user.email or "",
                "dni": request.user.dni,
                "rol": perfil.rol,
                "especialidad": perfil.especialidad,
            },
            "especialidades": [{"codigo": code, "nombre": label} for code, label in PerfilUsuario.ESPECIALIDADES],
        })

    data = _json_body(request)
    if data is None or set(data) != {"especialidad"}:
        return JsonResponse({"error": "La solicitud debe incluir únicamente una especialidad válida."}, status=400)
    especialidad = data.get("especialidad")
    if not isinstance(especialidad, str) or especialidad not in dict(PerfilUsuario.ESPECIALIDADES):
        return JsonResponse({"error": "Selecciona una especialidad válida: IPP, GAO o TP."}, status=400)
    from django.db import transaction
    with transaction.atomic():
        perfil = PerfilUsuario.objects.select_for_update().get(pk=perfil.pk, usuario=request.user)
        if perfil.especialidad:
            if perfil.especialidad != especialidad:
                return JsonResponse({"error": "La especialidad ya fue registrada y no se puede cambiar."}, status=409)
            return JsonResponse({"perfil": {"especialidad": perfil.especialidad}, "sin_cambios": True})
        perfil.especialidad = especialidad
        perfil.save(update_fields=("especialidad",))
    return JsonResponse({"perfil": {"especialidad": perfil.especialidad}}, status=200)


@login_required
@require_http_methods(["POST"])
def api_cambiar_contrasena(request):
    data = _json_body(request)
    if data is None or set(data) != {"contrasena_actual", "nueva_contrasena", "confirmacion"}:
        return JsonResponse({"error": "Completa la contraseña actual y los dos campos de la nueva contraseña."}, status=400)
    current = data.get("contrasena_actual")
    new = data.get("nueva_contrasena")
    confirmation = data.get("confirmacion")
    if not all(isinstance(value, str) for value in (current, new, confirmation)):
        return JsonResponse({"error": "Los campos de contraseña deben ser texto."}, status=400)
    if len(current) > 1024 or len(new) > 1024 or len(confirmation) > 1024:
        return JsonResponse({"error": "La contraseña supera el largo permitido."}, status=400)
    if not request.user.check_password(current):
        return JsonResponse({"error": "La contraseña actual es incorrecta."}, status=400)
    if new != confirmation:
        return JsonResponse({"error": "Las contraseñas nuevas no coinciden."}, status=400)
    try:
        validate_password(new, user=request.user)
    except ValidationError as exc:
        return JsonResponse({"error": " ".join(exc.messages)}, status=400)
    request.user.set_password(new)
    request.user.save(update_fields=("password",))
    update_session_auth_hash(request, request.user)
    return JsonResponse({"cambiada": True, "mensaje": "La contraseña se actualizó correctamente."})


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
        except Exception:
            logger.exception("Error inesperado al registrar usuario en EduFlow")
            raise     
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
