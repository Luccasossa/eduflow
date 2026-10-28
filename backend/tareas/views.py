import json
from datetime import date
from django.db import IntegrityError, transaction
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.conf import settings

from proyectos.models import Proyecto
from proyectos.models import DevolucionDocente
from proyectos.permissions import profesor_autorizado
from .models import Entrega, Tarea


def _rol(usuario):
    perfil = getattr(usuario, "perfil", None)
    return perfil.rol if perfil else None


def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _fecha(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("La fecha debe tener formato AAAA-MM-DD.")


def _serializar(tarea):
    return {
        "id": tarea.id,
        "titulo": tarea.titulo,
        "descripcion": tarea.descripcion,
        "prioridad": tarea.prioridad,
        "estado": tarea.estado,
        "fecha_vencimiento": tarea.fecha_vencimiento.isoformat() if tarea.fecha_vencimiento else "",
        "proyecto_id": tarea.proyecto_id,
        "calificacion": str(tarea.calificacion) if tarea.calificacion is not None else "",
        "retroalimentacion": tarea.retroalimentacion,
    }


def _proyecto_autorizado(request, proyecto_id):
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    rol = _rol(request.user)
    if rol == "profesor":
        if profesor_autorizado(request.user, proyecto):
            return proyecto
    if rol == "alumno" and (
        proyecto.creador_id == request.user.id
        or proyecto.integrantes.filter(pk=request.user.pk).exists()
    ):
        return proyecto
    raise Http404


def _tarea_autorizada(request, pk):
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto", "creador"), pk=pk)
    rol = _rol(request.user)
    if tarea.proyecto_id is None:
        if rol == "alumno" and tarea.creador_id == request.user.id:
            return tarea
    elif (rol == "profesor" and profesor_autorizado(request.user, tarea.proyecto)) or (
        rol == "alumno"
        and (tarea.proyecto.creador_id == request.user.id
             or tarea.proyecto.integrantes.filter(pk=request.user.pk).exists())
    ):
        return tarea
    raise Http404


def _validar_campos(data, tarea=None):
    titulo = str(data.get("titulo", tarea.titulo if tarea else "")).strip()
    descripcion = str(data.get("descripcion", tarea.descripcion if tarea else "")).strip()
    prioridad = data.get("prioridad", tarea.prioridad if tarea else "media")
    estado = data.get("estado", tarea.estado if tarea else "pendiente")
    if not titulo or len(titulo) > 150:
        raise ValueError("El título es obligatorio y admite hasta 150 caracteres.")
    if len(descripcion) > 20000:
        raise ValueError("La descripción supera el límite permitido.")
    if not isinstance(prioridad, str) or prioridad not in dict(Tarea.PRIORIDADES):
        raise ValueError("Selecciona una prioridad válida.")
    if not isinstance(estado, str) or estado not in dict(Tarea.ESTADOS):
        raise ValueError("Selecciona un estado válido.")
    fecha = _fecha(data.get("fecha_vencimiento", tarea.fecha_vencimiento.isoformat() if tarea and tarea.fecha_vencimiento else ""))
    return {"titulo": titulo, "descripcion": descripcion, "prioridad": prioridad, "estado": estado, "fecha_vencimiento": fecha}


@login_required
@require_http_methods(["GET", "POST"])
def api_tareas(request):
    rol = _rol(request.user)
    if rol not in ("alumno", "profesor"):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)

    if request.method == "GET":
        proyecto_id = request.GET.get("proyecto")
        if proyecto_id:
            try:
                proyecto = _proyecto_autorizado(request, proyecto_id)
            except (TypeError, ValueError, Http404):
                raise Http404
            tareas = Tarea.objects.filter(proyecto=proyecto)
        elif rol == "alumno":
            tareas = Tarea.objects.filter(creador=request.user, proyecto__isnull=True)
        else:
            tareas = Tarea.objects.filter(proyecto__isnull=False)
            if not request.user.is_superuser:
                tareas = tareas.filter(proyecto__profesores=request.user)

        estado = request.GET.get("estado", "")
        prioridad = request.GET.get("prioridad", "")
        if request.GET.get("desde") and request.GET.get("hasta"):
            try:
                if _fecha(request.GET["desde"]) > _fecha(request.GET["hasta"]):
                    return JsonResponse({"error": "La fecha inicial debe ser anterior a la fecha final."}, status=400)
            except (TypeError, ValueError) as exc:
                return JsonResponse({"error": str(exc) or "Una fecha no es válida."}, status=400)
        if estado:
            if estado not in dict(Tarea.ESTADOS):
                return JsonResponse({"error": "El filtro de estado no es válido."}, status=400)
            tareas = tareas.filter(estado=estado)
        if prioridad:
            if prioridad not in dict(Tarea.PRIORIDADES):
                return JsonResponse({"error": "El filtro de prioridad no es válido."}, status=400)
            tareas = tareas.filter(prioridad=prioridad)
        for key, lookup in (("desde", "fecha_vencimiento__gte"), ("hasta", "fecha_vencimiento__lte")):
            if request.GET.get(key):
                try:
                    tareas = tareas.filter(**{lookup: _fecha(request.GET[key])})
                except ValueError as exc:
                    return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"tareas": [_serializar(t) for t in tareas.order_by("fecha_vencimiento", "id")]})

    if rol != "alumno":
        return JsonResponse({"error": "Solo los alumnos pueden crear tareas."}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    proyecto = None
    if data.get("proyecto") not in (None, ""):
        try:
            proyecto = _proyecto_autorizado(request, data["proyecto"])
        except (TypeError, ValueError, Http404):
            raise Http404
    try:
        fields = _validar_campos(data)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    with transaction.atomic():
        tarea = Tarea.objects.create(creador=request.user, proyecto=proyecto, **fields)
        if proyecto:
            proyecto.actualizar_progreso()
    return JsonResponse({"tarea": _serializar(tarea)}, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_tarea(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        return JsonResponse({"tarea": _serializar(tarea)})
    rol = _rol(request.user)
    if rol != "alumno":
        return JsonResponse({"error": "Los profesores solo pueden revisar y calificar tareas."}, status=403)
    if request.method == "DELETE":
        proyecto = tarea.proyecto
        with transaction.atomic():
            tarea.delete()
            if proyecto:
                proyecto.actualizar_progreso()
        return JsonResponse({"eliminada": True})
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    try:
        fields = _validar_campos(data, tarea)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    with transaction.atomic():
        for key, value in fields.items():
            setattr(tarea, key, value)
        tarea.save(update_fields=(*fields.keys(),))
        if tarea.proyecto_id:
            tarea.proyecto.actualizar_progreso()
    return JsonResponse({"tarea": _serializar(tarea)})


@login_required
@require_http_methods(["PATCH"])
def api_calificar_tarea(request, pk):
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo los profesores pueden calificar tareas."}, status=403)
    tarea = get_object_or_404(Tarea.objects.select_related("proyecto").filter(proyecto__isnull=False), pk=pk)
    if not profesor_autorizado(request.user, tarea.proyecto):
        raise Http404
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    if "calificacion" not in data:
        return JsonResponse({"error": "Indica una calificación válida."}, status=400)
    retroalimentacion = data.get("retroalimentacion", "")
    try:
        calificacion = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=settings.EDUFLOW_GRADE_MAX).clean(data["calificacion"])
        if not isinstance(retroalimentacion, str) or len(retroalimentacion) > 20000:
            raise ValueError
        retroalimentacion = retroalimentacion.strip()
    except (ValidationError, ValueError, TypeError):
        return JsonResponse({"error": "La calificación o retroalimentación no es válida."}, status=400)
    with transaction.atomic():
        tarea = get_object_or_404(
            Tarea.objects.select_for_update().select_related("proyecto"), pk=pk,
        )
        if tarea.proyecto_id is None or not profesor_autorizado(request.user, tarea.proyecto):
            raise Http404
        devolucion = DevolucionDocente(proyecto=tarea.proyecto, tarea=tarea, autor=request.user,
                                       calificacion=calificacion, comentario=retroalimentacion)
        try:
            devolucion.full_clean()
        except ValidationError:
            return JsonResponse({"error": "La evaluación no es válida."}, status=400)
        devolucion.save()
        tarea.calificacion = calificacion
        tarea.retroalimentacion = retroalimentacion
        tarea.evaluado_por = request.user
        tarea.save(update_fields=("calificacion", "retroalimentacion", "evaluado_por"))
    return JsonResponse({"tarea": _serializar(tarea)})


def _serializar_entrega(entrega):
    return {
        "id": entrega.pk,
        "tarea_id": entrega.tarea_id,
        "alumno_id": entrega.alumno_id,
        "nombre": entrega.archivo.name.rsplit("/", 1)[-1],
        "fecha_entrega": entrega.fecha_entrega.isoformat(),
        "estado": entrega.estado,
        "observaciones": entrega.observaciones,
        "descarga": f"/tareas/entregas/{entrega.pk}/descargar/",
    }


@login_required
@require_http_methods(["GET", "POST"])
def api_entregas(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        entregas = Entrega.objects.filter(tarea=tarea).select_related("alumno")
        if _rol(request.user) == "alumno":
            entregas = entregas.filter(alumno=request.user)
        return JsonResponse({"entregas": [_serializar_entrega(item) for item in entregas]})

    if _rol(request.user) != "alumno":
        return JsonResponse({"error": "Solo los alumnos autorizados pueden entregar archivos."}, status=403)
    archivo = request.FILES.get("archivo")
    if archivo is None:
        return JsonResponse({"error": "Selecciona un archivo para entregar."}, status=400)
    observaciones = request.POST.get("observaciones", "").strip()
    if len(observaciones) > 20000:
        return JsonResponse({"error": "Las observaciones superan el límite permitido."}, status=400)
    if Entrega.objects.filter(tarea=tarea, alumno=request.user).exists():
        return JsonResponse({"error": "Ya existe una entrega para esta tarea."}, status=409)
    entrega = Entrega(tarea=tarea, alumno=request.user, archivo=archivo, observaciones=observaciones)
    try:
        entrega.full_clean()
        with transaction.atomic():
            entrega.save()
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)
    except IntegrityError:
        if entrega.archivo.name:
            entrega.archivo.storage.delete(entrega.archivo.name)
        return JsonResponse({"error": "Ya existe una entrega para esta tarea."}, status=409)
    return JsonResponse({"entrega": _serializar_entrega(entrega)}, status=201)


@login_required
@require_http_methods(["GET"])
def descargar_entrega(request, pk):
    entrega = get_object_or_404(Entrega.objects.select_related("tarea__proyecto", "alumno"), pk=pk)
    tarea = entrega.tarea
    rol = _rol(request.user)
    autorizado = (
        rol == "alumno" and entrega.alumno_id == request.user.id
        and (tarea.proyecto_id is None or (
            tarea.proyecto.creador_id == request.user.id
            or tarea.proyecto.integrantes.filter(pk=request.user.pk).exists()
        ))
    ) or (
        rol == "profesor" and tarea.proyecto_id is not None
        and profesor_autorizado(request.user, tarea.proyecto)
    )
    if not autorizado:
        raise Http404
    try:
        response = FileResponse(
            entrega.archivo.open("rb"), as_attachment=True,
            filename=entrega.archivo.name.rsplit("/", 1)[-1],
        )
    except (FileNotFoundError, ValueError):
        raise Http404
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def lista_tareas(request):
    if _rol(request.user) == "profesor":
        return redirect("core:profesor")
    return redirect("core:alumno")
