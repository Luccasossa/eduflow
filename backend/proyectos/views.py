import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_http_methods

from usuarios.models import Usuario
from .models import Proyecto


def _rol(usuario):
    perfil = getattr(usuario, "perfil", None)
    return perfil.rol if perfil else None


def _json_body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _fecha(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("La fecha de entrega no es válida.")


def _es_integrante(proyecto, usuario):
    return proyecto.creador_id == usuario.id or proyecto.integrantes.filter(pk=usuario.pk).exists()


def _proyecto_visible(request, pk):
    proyecto = get_object_or_404(Proyecto.objects.prefetch_related("integrantes"), pk=pk)
    if _rol(request.user) == "profesor":
        return proyecto
    if _rol(request.user) == "alumno" and _es_integrante(proyecto, request.user):
        return proyecto
    raise Http404


def _serializar_proyecto(proyecto, usuario=None):
    tareas = list(proyecto.tareas.all().order_by("fecha_vencimiento", "id"))
    total = len(tareas)
    completadas = sum(t.estado == "completada" for t in tareas)
    progreso = round(completadas * 100 / total) if total else 0
    return {
        "id": proyecto.id,
        "nombre": proyecto.nombre,
        "descripcion": proyecto.descripcion,
        "fecha_entrega": proyecto.fecha_entrega.isoformat() if proyecto.fecha_entrega else "",
        "progreso": progreso,
        "creador_id": proyecto.creador_id,
        "puede_editar": bool(usuario and _rol(usuario) == "alumno" and proyecto.creador_id == usuario.id),
        "integrantes": [
            {"id": miembro.id, "nombre": miembro.get_full_name() or miembro.dni}
            for miembro in proyecto.integrantes.all().order_by("first_name", "last_name", "dni")
        ],
        "tareas": [
            {
                "id": tarea.id,
                "proyecto_id": tarea.proyecto_id,
                "titulo": tarea.titulo,
                "descripcion": tarea.descripcion,
                "fecha_vencimiento": tarea.fecha_vencimiento.isoformat() if tarea.fecha_vencimiento else "",
                "prioridad": tarea.prioridad,
                "estado": tarea.estado,
                "creador": tarea.creador.get_full_name() or tarea.creador.dni,
                "calificacion": str(tarea.calificacion) if tarea.calificacion is not None else "",
                "retroalimentacion": tarea.retroalimentacion,
            }
            for tarea in tareas
        ],
    }


@login_required
@require_GET
def api_alumnos(request):
    if _rol(request.user) != "alumno":
        return JsonResponse({"error": "Solo los alumnos pueden crear proyectos grupales."}, status=403)
    alumnos = Usuario.objects.filter(perfil__rol="alumno", is_active=True).order_by("first_name", "last_name", "dni")
    return JsonResponse({"alumnos": [
        {"id": alumno.id, "nombre": alumno.get_full_name() or alumno.dni}
        for alumno in alumnos
    ]})


@login_required
@require_http_methods(["GET", "POST"])
def api_proyectos(request):
    rol = _rol(request.user)
    if rol not in ("alumno", "profesor"):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)

    if request.method == "GET":
        if rol == "profesor":
            proyectos = Proyecto.objects.all()
        else:
            from django.db.models import Q
            proyectos = Proyecto.objects.filter(Q(creador=request.user) | Q(integrantes=request.user)).distinct()
        return JsonResponse({"proyectos": [_serializar_proyecto(p, request.user) for p in proyectos.order_by("-fecha_actualizacion")]})

    if rol != "alumno":
        return JsonResponse({"error": "Solo los alumnos pueden crear proyectos."}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    nombre = str(data.get("nombre", "")).strip()
    descripcion = str(data.get("descripcion", "")).strip()
    if not nombre or len(nombre) > 150:
        return JsonResponse({"error": "El nombre es obligatorio y admite hasta 150 caracteres."}, status=400)
    if len(descripcion) > 10000:
        return JsonResponse({"error": "La descripción supera el límite permitido."}, status=400)
    try:
        fecha_entrega = _fecha(data.get("fecha_entrega"))
        ids = data.get("integrantes", [])
        if not isinstance(ids, list) or any(not str(value).isdigit() for value in ids):
            raise ValueError("La lista de integrantes no es válida.")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    miembros = list(Usuario.objects.filter(pk__in=ids, perfil__rol="alumno", is_active=True))
    if len({int(value) for value in ids}) != len(miembros):
        return JsonResponse({"error": "Todos los integrantes deben ser alumnos activos."}, status=400)
    with transaction.atomic():
        proyecto = Proyecto.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            fecha_entrega=fecha_entrega,
            creador=request.user,
        )
        proyecto.integrantes.add(request.user, *miembros)
    return JsonResponse({"proyecto": _serializar_proyecto(proyecto, request.user)}, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_proyecto(request, pk):
    proyecto = _proyecto_visible(request, pk)
    if request.method == "GET":
        return JsonResponse({"proyecto": _serializar_proyecto(proyecto, request.user)})
    if _rol(request.user) != "alumno" or proyecto.creador_id != request.user.id:
        return JsonResponse({"error": "Solo quien creó el proyecto puede modificarlo."}, status=403)
    if request.method == "DELETE":
        proyecto.delete()
        return JsonResponse({"eliminado": True})

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    if "nombre" in data:
        nombre = str(data["nombre"]).strip()
        if not nombre or len(nombre) > 150:
            return JsonResponse({"error": "El nombre es obligatorio y admite hasta 150 caracteres."}, status=400)
        proyecto.nombre = nombre
    if "descripcion" in data:
        proyecto.descripcion = str(data["descripcion"]).strip()
        if len(proyecto.descripcion) > 10000:
            return JsonResponse({"error": "La descripción supera el límite permitido."}, status=400)
    if "fecha_entrega" in data:
        try:
            proyecto.fecha_entrega = _fecha(data["fecha_entrega"])
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
    if "integrantes" in data:
        ids = data["integrantes"]
        if not isinstance(ids, list) or any(not str(value).isdigit() for value in ids):
            return JsonResponse({"error": "La lista de integrantes no es válida."}, status=400)
        miembros = list(Usuario.objects.filter(pk__in=ids, perfil__rol="alumno", is_active=True))
        if len({int(value) for value in ids}) != len(miembros):
            return JsonResponse({"error": "Todos los integrantes deben ser alumnos activos."}, status=400)
        proyecto.integrantes.set([request.user, *miembros])
    proyecto.save()
    return JsonResponse({"proyecto": _serializar_proyecto(proyecto, request.user)})


@login_required
def lista_proyectos(request):
    if _rol(request.user) == "profesor":
        return redirect("core:profesor")
    return redirect("core:alumno")
