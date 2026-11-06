from functools import wraps

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods


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
    return render(request, "index.html", {"calificacion_maxima": settings.EDUFLOW_GRADE_MAX})


@requiere_rol("profesor")
def inicioprofe(request):
    return render(request, "eduflow-todo-en-uno (1).html", {"calificacion_maxima": settings.EDUFLOW_GRADE_MAX})


@login_required
@require_GET
def api_actividad(request):
    from .models import Actividad
    rows = Actividad.objects.filter(usuario=request.user).order_by("-fecha", "-pk")[:20]
    return JsonResponse({"actividades": [{"descripcion": row.descripcion, "tipo": row.tipo, "fecha": row.fecha.isoformat(), "tarea_id": row.tarea_id, "proyecto_id": row.proyecto_id, "archivo_id": row.archivo_id} for row in rows]})


@login_required
@require_http_methods(["GET", "PATCH"])
def api_notificaciones(request):
    from .models import Notificacion
    rows = Notificacion.objects.filter(usuario=request.user).select_related("tarea").order_by("-fecha_creacion", "-pk")
    if request.method == "GET":
        return JsonResponse({"no_leidas": rows.filter(leida=False).count(), "notificaciones": [{"id": n.pk, "mensaje": n.mensaje, "tipo": n.tipo, "leida": n.leida, "fecha": n.fecha_creacion.isoformat(), "url": f"/tareas/api/{n.tarea_id}/" if n.tarea_id else ""} for n in rows[:30]]})
    import json
    try: ids = json.loads(request.body or b"{}").get("ids", [])
    except (ValueError, AttributeError): return JsonResponse({"error": "Solicitud no válida."}, status=400)
    if not isinstance(ids, list): return JsonResponse({"error": "Solicitud no válida."}, status=400)
    rows.filter(pk__in=ids).update(leida=True)
    return JsonResponse({"actualizadas": True})
