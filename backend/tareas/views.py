import json
import mimetypes
from datetime import date
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django import forms
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.conf import settings

from proyectos.models import Proyecto
from proyectos.models import DevolucionDocente
from proyectos.permissions import profesor_autorizado
from .models import AsignacionTarea, CorreccionEntrega, Entrega, Tarea
from .prioridad import prioridad_para, sincronizar_prioridades


def _rol(usuario):
    perfil = getattr(usuario, "perfil", None)
    return perfil.rol if perfil else None


def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _es_conflicto_concurrencia(error):
    code = error.args[0] if error.args and isinstance(error.args[0], int) else None
    return code in (5, 6, 1205, 1213) or "database is locked" in str(error).lower()


def _manejar_conflicto_concurrencia(view):
    from functools import wraps

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except OperationalError as exc:
            if not _es_conflicto_concurrencia(exc):
                raise
            return JsonResponse(
                {"error": "La operación coincidió con otra solicitud. Actualiza y vuelve a intentar."},
                status=409,
            )
    return wrapped


def _fecha(value):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("La fecha debe tener formato AAAA-MM-DD.")


def _serializar(tarea, usuario=None):
    from archivos.models import Archivo

    sincronizar_prioridades((tarea,))
    devoluciones = tarea.devoluciones.select_related("autor", "alumno").order_by("fecha_creacion", "pk")
    if usuario and _rol(usuario) == "alumno":
        devoluciones = devoluciones.filter(anulada_en__isnull=True).filter(
            Q(tipo="historica", tarea=tarea) | Q(tipo="grupal") | Q(tipo="individual", alumno=usuario)
        )
    return {
        "id": tarea.id,
        "titulo": tarea.titulo,
        "descripcion": tarea.descripcion,
        "prioridad": tarea.prioridad,
        "estado": tarea.estado,
        "fecha_vencimiento": tarea.fecha_vencimiento.isoformat() if tarea.fecha_vencimiento else "",
        "proyecto_id": tarea.proyecto_id,
        "puede_adjuntar": bool(usuario and _rol(usuario) == "alumno" and (tarea.creador_id == usuario.pk or tarea.proyecto_id and (tarea.proyecto.creador_id == usuario.pk or tarea.proyecto.integrantes.filter(pk=usuario.pk).exists()))),
        "puede_editar": bool(usuario and _rol(usuario) == "alumno" and (tarea.creador_id == usuario.pk or tarea.proyecto_id and (tarea.proyecto.creador_id == usuario.pk or tarea.proyecto.integrantes.filter(pk=usuario.pk).exists())) and not tarea.asignaciones.exists()),
        "puede_entregar": bool(usuario and _rol(usuario) == "alumno" and tarea.proyecto_id is None and tarea.asignaciones.filter(alumno=usuario).exists() and not tarea.entregas.filter(alumno=usuario).exists()),
        "calificacion": str(tarea.calificacion) if tarea.calificacion is not None else "",
        "retroalimentacion": tarea.retroalimentacion,
        "archivos_adjuntos": [
            {"id": f.pk, "nombre": f.nombre_original, "tipo": f.tipo, "extension": f.nombre_original.rsplit(".", 1)[-1].upper() if "." in f.nombre_original else "Archivo", "tamano": f.tamano, "fecha_subida": f.fecha_subida.isoformat(), "abrir": f"/archivos/api/{f.pk}/descargar/?inline=1", "descarga": f"/archivos/api/{f.pk}/descargar/", "puede_quitar": bool(usuario and f.propietario_id == usuario.pk)}
            for f in Archivo.objects.filter(Q(tareas_adjuntas=tarea) | Q(tarea=tarea)).distinct()
        ],
        "fecha_creacion": tarea.fecha_creacion.isoformat(),
        "devoluciones": [_serializar_evaluacion(entry, usuario) for entry in devoluciones],
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
        if rol == "alumno" and (tarea.creador_id == request.user.id or tarea.asignaciones.filter(alumno=request.user).exists()):
            return tarea
        if rol == "profesor" and tarea.asignaciones.filter(profesor=request.user).exists():
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
    estado = data.get("estado", tarea.estado if tarea else "pendiente")
    if not titulo or len(titulo) > 150:
        raise ValueError("El título es obligatorio y admite hasta 150 caracteres.")
    if len(descripcion) > 20000:
        raise ValueError("La descripción supera el límite permitido.")
    if not isinstance(estado, str) or estado not in dict(Tarea.ESTADOS):
        raise ValueError("Selecciona un estado válido.")
    fecha = _fecha(data.get("fecha_vencimiento", tarea.fecha_vencimiento.isoformat() if tarea and tarea.fecha_vencimiento else ""))
    prioridad = prioridad_para(fecha)
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
            tareas = Tarea.objects.filter(Q(creador=request.user) | Q(asignaciones__alumno=request.user), proyecto__isnull=True).distinct()
        else:
            tareas = Tarea.objects.filter(proyecto__isnull=False)
            if not request.user.is_superuser:
                tareas = tareas.filter(proyecto__profesores=request.user)

        sincronizar_prioridades(list(tareas))

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
        return JsonResponse({"tareas": [_serializar(t, request.user) for t in tareas.order_by("fecha_vencimiento", "id")]})

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
        from core.models import Actividad
        Actividad.objects.create(usuario=request.user, descripcion=f"Creaste la tarea {tarea.titulo}.", tipo="tarea", tarea=tarea)
        if proyecto:
            proyecto.actualizar_progreso()
    return JsonResponse({"tarea": _serializar(tarea, request.user)}, status=201)


@login_required
@require_http_methods(["GET", "POST"])
def api_asignaciones(request):
    """Teacher task assignments and deliveries; project tasks stay in project review."""
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo los docentes pueden gestionar asignaciones."}, status=403)
    if request.method == "GET":
        assignments = AsignacionTarea.objects.filter(profesor=request.user, tarea__proyecto__isnull=True).select_related("tarea", "alumno").prefetch_related("tarea__entregas__correcciones")
        rows = []
        for assignment in assignments.order_by("-fecha_asignacion", "-pk"):
            deliveries = assignment.tarea.entregas.filter(alumno=assignment.alumno).select_related("alumno")
            rows.append({
                "id": assignment.pk, "tarea_id": assignment.tarea_id,
                "titulo": assignment.tarea.titulo, "descripcion": assignment.tarea.descripcion,
                "fecha_vencimiento": assignment.tarea.fecha_vencimiento.isoformat() if assignment.tarea.fecha_vencimiento else "",
                "estado": assignment.tarea.estado, "alumno_id": assignment.alumno_id,
                "alumno": assignment.alumno.get_full_name() or assignment.alumno.dni,
                "archivos_adjuntos": _serializar(assignment.tarea, request.user)["archivos_adjuntos"],
                "entregas": [_serializar_entrega(delivery) for delivery in deliveries],
            })
        return JsonResponse({"asignaciones": rows})

    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    from usuarios.models import Usuario
    alumno = get_object_or_404(Usuario.objects.filter(perfil__rol="alumno", is_active=True), pk=data.get("alumno_id"))
    try:
        fields = _validar_campos(data)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    with transaction.atomic():
        tarea = Tarea.objects.create(creador=request.user, proyecto=None, **fields)
        assignment = AsignacionTarea(tarea=tarea, alumno=alumno, profesor=request.user)
        try:
            assignment.full_clean()
            assignment.save()
        except ValidationError:
            tarea.delete()
            return JsonResponse({"error": "No se pudo validar la asignación de la tarea."}, status=400)
    return JsonResponse({"asignacion": {"id": assignment.pk, "tarea_id": tarea.pk, "alumno": alumno.get_full_name() or alumno.dni, "titulo": tarea.titulo}}, status=201)


@login_required
@require_http_methods(["GET"])
def api_alumnos_asignables(request):
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo los docentes pueden consultar alumnos."}, status=403)
    from usuarios.models import Usuario
    return JsonResponse({"alumnos": [{"id": user.pk, "nombre": user.get_full_name() or user.dni} for user in Usuario.objects.filter(perfil__rol="alumno", is_active=True).order_by("first_name", "last_name", "dni")]})


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_tarea(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        return JsonResponse({"tarea": _serializar(tarea, request.user)})
    rol = _rol(request.user)
    if rol != "alumno":
        return JsonResponse({"error": "Los profesores solo pueden revisar y calificar tareas."}, status=403)
    if request.method == "DELETE":
        if tarea.proyecto_id is None and tarea.asignaciones.filter(alumno=request.user).exists():
            return JsonResponse({"error": "No puedes eliminar una tarea asignada por tu docente."}, status=403)
        proyecto = tarea.proyecto
        with transaction.atomic():
            tarea.delete()
            if proyecto:
                proyecto.actualizar_progreso()
        return JsonResponse({"eliminada": True})
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    assigned_task = tarea.proyecto_id is None and tarea.asignaciones.filter(alumno=request.user).exists()
    if assigned_task and set(data) - {"estado"}:
        return JsonResponse({"error": "No puedes editar los datos de una tarea asignada."}, status=403)
    try:
        fields = _validar_campos(data, tarea)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    with transaction.atomic():
        old_state = tarea.estado
        for key, value in fields.items():
            setattr(tarea, key, value)
        tarea.save(update_fields=(*fields.keys(),))
        if old_state != "completada" and tarea.estado == "completada":
            from core.models import Actividad
            Actividad.objects.create(usuario=request.user, descripcion=f"Completaste la tarea {tarea.titulo}.", tipo="tarea", tarea=tarea)
        if tarea.proyecto_id:
            tarea.proyecto.actualizar_progreso()
    return JsonResponse({"tarea": _serializar(tarea, request.user)})


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
        integrantes = list(tarea.proyecto.integrantes.all())
        if tarea.proyecto.creador_id not in {persona.pk for persona in integrantes}:
            integrantes.append(tarea.proyecto.creador)
        from core.models import Actividad, Notificacion
        for alumno in integrantes:
            message = f"Tu tarea {tarea.titulo} fue calificada. Nota: {calificacion}."
            Notificacion.objects.create(usuario=alumno, tarea=tarea, tipo="calificacion", mensaje=message)
            Actividad.objects.create(usuario=alumno, tarea=tarea, tipo="calificacion", descripcion=message)
    return JsonResponse({"tarea": _serializar(tarea, request.user)})


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def api_archivos_tarea(request, pk):
    from archivos.models import Archivo
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        return JsonResponse({"archivos": _serializar(tarea, request.user)["archivos_adjuntos"]})
    if _rol(request.user) != "alumno" or (tarea.proyecto_id is None and tarea.creador_id != request.user.pk):
        return JsonResponse({"error": "Solo el alumno puede gestionar sus archivos adjuntos."}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "Solicitud no válida."}, status=400)
    archivo = get_object_or_404(Archivo, pk=data.get("archivo_id"), propietario=request.user)
    if request.method == "POST":
        already_attached = tarea.archivos_adjuntos.filter(pk=archivo.pk).exists()
        tarea.archivos_adjuntos.add(archivo)
        if archivo.tarea_id is None:
            archivo.tarea = tarea
            archivo.proyecto = tarea.proyecto
            archivo.save(update_fields=("tarea", "proyecto"))
        if not already_attached:
            from core.models import Actividad
            Actividad.objects.create(usuario=request.user, descripcion=f"Adjuntaste {archivo.nombre_original} a la tarea {tarea.titulo}.", tipo="adjunto", tarea=tarea, archivo=archivo)
        return JsonResponse({"adjuntado": True})
    tarea.archivos_adjuntos.remove(archivo)
    if archivo.tarea_id == tarea.pk:
        archivo.tarea = None
        has_other_task_in_project = tarea.proyecto_id and archivo.tareas_adjuntas.filter(proyecto_id=tarea.proyecto_id).exists()
        has_project_attachment = tarea.proyecto_id and archivo.proyectos_adjuntos.filter(pk=tarea.proyecto_id).exists()
        if archivo.proyecto_id == tarea.proyecto_id and not (has_other_task_in_project or has_project_attachment):
            archivo.proyecto = None
        archivo.save(update_fields=("tarea", "proyecto"))
    return JsonResponse({"quitado": True})


def _serializar_entrega(entrega):
    correction = entrega.correcciones.filter(anulada_en__isnull=True).select_related("profesor").order_by("-fecha_correccion", "-pk").first()
    return {
        "id": entrega.pk,
        "tarea_id": entrega.tarea_id,
        "alumno_id": entrega.alumno_id,
        "alumno": entrega.alumno.get_full_name() or entrega.alumno.dni,
        "grupo_id": entrega.tarea.proyecto_id,
        "nombre": entrega.archivo.name.rsplit("/", 1)[-1],
        "fecha_entrega": entrega.fecha_entrega.isoformat(),
        "estado": entrega.estado,
        "observaciones": entrega.observaciones,
        "descarga": f"/tareas/entregas/{entrega.pk}/descargar/",
        "correccion": _serializar_correccion(correction) if correction else None,
    }


def _serializar_correccion(item):
    return {"id": item.pk, "calificacion": str(item.calificacion) if item.calificacion is not None else "", "comentario": item.comentario,
            "estado": item.estado, "profesor": item.profesor.get_full_name() or item.profesor.dni,
            "fecha": item.fecha_correccion.isoformat(), "anulada": item.anulada_en is not None}


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
@_manejar_conflicto_concurrencia
def api_correccion_entrega(request, pk):
    entrega = get_object_or_404(Entrega.objects.select_related("tarea", "alumno"), pk=pk, tarea__proyecto__isnull=True)
    assignment = AsignacionTarea.objects.filter(tarea=entrega.tarea, alumno=entrega.alumno).first()
    if not assignment or not (
        (_rol(request.user) == "profesor" and assignment.profesor_id == request.user.pk)
        or (_rol(request.user) == "alumno" and entrega.alumno_id == request.user.pk)
    ):
        raise Http404
    corrections = CorreccionEntrega.objects.filter(entrega=entrega, anulada_en__isnull=True).select_related("profesor").order_by("-fecha_correccion", "-pk")
    current = corrections.first()
    if request.method == "GET":
        return JsonResponse({"correccion": _serializar_correccion(current) if current else None,
                             "historial": [_serializar_correccion(item) for item in entrega.correcciones.select_related("profesor").order_by("fecha_correccion", "pk")] if _rol(request.user) == "profesor" else []})
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo el docente asignado puede corregir esta entrega."}, status=403)
    if request.method == "DELETE":
        if not current:
            raise Http404
        current.anulada_en, current.anulada_por = timezone.now(), request.user
        current.save(update_fields=("anulada_en", "anulada_por"))
        entrega.estado = "entregada"
        entrega.save(update_fields=("estado",))
        return JsonResponse({"eliminada": True})
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    try:
        raw_grade = data.get("calificacion", "")
        grade = None if raw_grade in (None, "") else forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, max_value=settings.EDUFLOW_GRADE_MAX).clean(raw_grade)
        comment = data.get("comentario", "")
        state = data.get("estado", "corregida")
        if not isinstance(comment, str) or len(comment) > 20000 or state not in dict(CorreccionEntrega.ESTADOS) or (grade is None and not comment.strip()):
            raise ValueError
    except (ValidationError, TypeError, ValueError):
        return JsonResponse({"error": "Indica una nota o un comentario válido y un estado permitido."}, status=400)
    with transaction.atomic():
        if current:
            current.anulada_en, current.anulada_por = timezone.now(), request.user
            current.save(update_fields=("anulada_en", "anulada_por"))
        correction = CorreccionEntrega(entrega=entrega, profesor=request.user, calificacion=grade,
                                       comentario=comment.strip(), estado=state, reemplaza=current)
        correction.full_clean()
        correction.save()
        entrega.estado = {"en_revision": "en_revision", "corregida": "aprobada", "devuelta": "rechazada"}[state]
        entrega.save(update_fields=("estado",))
        from core.models import Actividad, Notificacion
        message = f"El docente publicó una devolución para tu tarea {entrega.tarea.titulo}."
        if grade is not None:
            message = f"Tu tarea {entrega.tarea.titulo} fue calificada: {grade}."
        Notificacion.objects.create(usuario=entrega.alumno, tarea=entrega.tarea, tipo="calificacion" if grade is not None else "comentario", mensaje=message)
        Actividad.objects.create(usuario=entrega.alumno, tarea=entrega.tarea, tipo="calificacion" if grade is not None else "comentario", descripcion=message)
    return JsonResponse({"correccion": _serializar_correccion(correction)}, status=201)


def _serializar_evaluacion(evaluacion, usuario=None):
    return {
        "id": evaluacion.pk,
        "tipo": evaluacion.tipo,
        "tarea_id": evaluacion.tarea_id,
        "alumno_id": evaluacion.alumno_id,
        "alumno": (evaluacion.alumno.get_full_name() or evaluacion.alumno.dni)
        if evaluacion.alumno_id else "",
        "calificacion": str(evaluacion.calificacion) if evaluacion.calificacion is not None else "",
        "comentario": evaluacion.comentario,
        "autor": evaluacion.autor.get_full_name() or evaluacion.autor.dni,
        "fecha": evaluacion.fecha_creacion.isoformat(),
        "anulada": evaluacion.anulada_en is not None,
        "puede_editar": bool(usuario and _rol(usuario) == "profesor" and evaluacion.autor_id == usuario.pk and evaluacion.anulada_en is None),
    }


def _evaluaciones_vigentes(tarea):
    from proyectos.models import DevolucionDocente

    entries = DevolucionDocente.objects.filter(tarea=tarea, anulada_en__isnull=True)
    grupal = entries.filter(tipo="grupal").select_related("autor").order_by("-fecha_creacion", "-pk").first()
    individuales = entries.filter(tipo="individual").select_related("autor", "alumno").order_by("alumno_id", "-fecha_creacion", "-pk")
    return grupal, individuales


@login_required
@require_http_methods(["GET"])
def api_evaluaciones(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if tarea.proyecto_id is None:
        raise Http404
    grupal, individuales = _evaluaciones_vigentes(tarea)
    if _rol(request.user) == "alumno":
        individuales = individuales.filter(alumno=request.user)
    return JsonResponse({
        "grupal": _serializar_evaluacion(grupal, request.user) if grupal else None,
        "individuales": [_serializar_evaluacion(item, request.user) for item in individuales],
        "historial": [
            _serializar_evaluacion(item, request.user)
            for item in tarea.devoluciones.select_related("autor", "alumno").order_by("fecha_creacion", "pk")
            if _rol(request.user) != "alumno" or (
                item.anulada_en is None and (item.tipo == "grupal" or (item.tipo == "individual" and item.alumno_id == request.user.pk))
            )
        ],
    })


def _guardar_o_anular_evaluacion(request, pk, tipo, alumno_id=None):
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo el docente autorizado puede gestionar evaluaciones."}, status=403)

    tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=pk, proyecto__isnull=False)
    if not profesor_autorizado(request.user, tarea.proyecto):
        raise Http404

    alumno = None
    if tipo == "individual":
        from usuarios.models import Usuario

        alumno = get_object_or_404(Usuario.objects.filter(perfil__rol="alumno", is_active=True), pk=alumno_id)
        if not (tarea.proyecto.creador_id == alumno.pk or tarea.proyecto.integrantes.filter(pk=alumno.pk).exists()):
            raise Http404

    if request.method != "DELETE":
        data = _json_body(request)
        if data is None:
            return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
        try:
            raw_grade = data.get("calificacion", "")
            grade = None if raw_grade in (None, "") else forms.DecimalField(
                max_digits=5,
                decimal_places=2,
                min_value=0,
                max_value=settings.EDUFLOW_GRADE_MAX,
            ).clean(raw_grade)
            comment = data.get("comentario", data.get("retroalimentacion", ""))
            if not isinstance(comment, str) or len(comment) > 20000:
                raise ValueError
            comment = comment.strip()
            if grade is None and not comment:
                raise ValueError
        except (ValidationError, ValueError, TypeError):
            return JsonResponse({"error": "La calificación o devolución no es válida."}, status=400)

    from proyectos.models import DevolucionDocente

    with transaction.atomic():
        tarea = get_object_or_404(
            Tarea.objects.select_for_update().select_related("proyecto"),
            pk=pk,
            proyecto__isnull=False,
        )
        if not profesor_autorizado(request.user, tarea.proyecto):
            raise Http404
        if alumno_id is not None and not (
            tarea.proyecto.creador_id == alumno_id
            or tarea.proyecto.integrantes.filter(pk=alumno_id).exists()
        ):
            raise Http404

        actuales = DevolucionDocente.objects.filter(
            tarea=tarea,
            tipo=tipo,
            anulada_en__isnull=True,
        )
        if alumno_id is not None:
            actuales = actuales.filter(alumno_id=alumno_id)
        else:
            actuales = actuales.filter(alumno__isnull=True)

        if request.method == "DELETE":
            actual = actuales.order_by("-fecha_creacion", "-pk").first()
            if not actual:
                raise Http404
            actual.anulada_en = timezone.now()
            actual.anulada_por = request.user
            actual.save(update_fields=("anulada_en", "anulada_por"))
            return JsonResponse({"eliminada": True})

        evaluacion = DevolucionDocente(
            proyecto=tarea.proyecto,
            tarea=tarea,
            autor=request.user,
            tipo=tipo,
            alumno=alumno,
            calificacion=grade,
            comentario=comment,
        )
        try:
            evaluacion.full_clean()
        except ValidationError:
            return JsonResponse({"error": "La evaluación no coincide con la tarea y el grupo."}, status=400)
        vigente = actuales.select_related("autor", "alumno").order_by("-fecha_creacion", "-pk")
        existente = vigente.first()
        if existente and existente.calificacion == grade and existente.comentario == comment:
            return JsonResponse({
                "evaluacion": _serializar_evaluacion(existente, request.user),
                "sin_cambios": True,
            })
        evaluacion.save()
        if grade is not None or comment:
            tarea.calificacion = grade
            tarea.retroalimentacion = comment
            tarea.evaluado_por = request.user
            tarea.save(update_fields=("calificacion", "retroalimentacion", "evaluado_por"))
        from core.models import Notificacion
        recipients = [alumno] if alumno else list(tarea.proyecto.integrantes.all())
        if not alumno and tarea.proyecto.creador_id not in {u.pk for u in recipients}:
            recipients.append(tarea.proyecto.creador)
        for recipient in recipients:
            message = f"El profesor dejó una devolución en la tarea {tarea.titulo}."
            if grade is not None:
                message = f"Tu tarea {tarea.titulo} fue calificada. Nota: {grade}."
            Notificacion.objects.create(usuario=recipient, tarea=tarea, tipo="calificacion" if grade is not None else "comentario", mensaje=message)
            from core.models import Actividad
            Actividad.objects.create(usuario=recipient, tarea=tarea, tipo="calificacion" if grade is not None else "comentario", descripcion=message)
    return JsonResponse({"evaluacion": _serializar_evaluacion(evaluacion)}, status=201)


@login_required
@require_http_methods(["POST", "PUT", "DELETE"])
@_manejar_conflicto_concurrencia
def api_evaluacion_grupal(request, pk):
    return _guardar_o_anular_evaluacion(request, pk, "grupal")


@login_required
@require_http_methods(["POST", "PUT", "DELETE"])
@_manejar_conflicto_concurrencia
def api_evaluacion_individual(request, pk, alumno_id):
    return _guardar_o_anular_evaluacion(request, pk, "individual", alumno_id)


@login_required
@require_http_methods(["GET", "POST"])
def api_entregas(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        entregas = Entrega.objects.filter(tarea=tarea).select_related("alumno", "tarea__proyecto")
        if _rol(request.user) == "alumno" and tarea.proyecto_id is None:
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
    entrega = Entrega(tarea=tarea, alumno=request.user, archivo=archivo, observaciones=observaciones)
    try:
        with transaction.atomic():
            tarea = get_object_or_404(
                Tarea.objects.select_for_update().select_related("proyecto"),
                pk=pk,
            )
            tarea = _tarea_autorizada(request, tarea.pk)
            existentes = Entrega.objects.filter(tarea=tarea)
            if tarea.proyecto_id is None:
                existentes = existentes.filter(alumno=request.user)
            if existentes.exists():
                return JsonResponse({
                    "error": "El grupo ya realizó la entrega." if tarea.proyecto_id else "Ya existe una entrega para esta tarea.",
                    "entregas": [_serializar_entrega(item) for item in existentes.select_related("alumno", "tarea__proyecto")],
                }, status=409)
            entrega.tarea = tarea
            entrega.full_clean()
            entrega.save()
    except ValidationError as exc:
        return JsonResponse({"error": exc.messages}, status=400)
    except IntegrityError:
        if entrega.archivo.name and entrega.archivo._committed:
            entrega.archivo.storage.delete(entrega.archivo.name)
        return JsonResponse({"error": "Ya existe una entrega para esta tarea."}, status=409)
    except OperationalError as exc:
        if entrega.archivo.name and entrega.archivo._committed:
            entrega.archivo.storage.delete(entrega.archivo.name)
        if _es_conflicto_concurrencia(exc):
            return JsonResponse(
                {"error": "La operación coincidió con otra entrega. Actualiza y vuelve a intentar."},
                status=409,
            )
        raise
    return JsonResponse({"entrega": _serializar_entrega(entrega)}, status=201)


@login_required
@require_http_methods(["GET"])
def descargar_entrega(request, pk):
    entrega = get_object_or_404(Entrega.objects.select_related("tarea__proyecto", "alumno"), pk=pk)
    tarea = entrega.tarea
    rol = _rol(request.user)
    autorizado = (
        rol == "alumno" and (
            (tarea.proyecto_id is None and entrega.alumno_id == request.user.id and (tarea.creador_id == request.user.id or AsignacionTarea.objects.filter(tarea=tarea, alumno=request.user).exists()))
            or (tarea.proyecto_id is not None and (
            tarea.proyecto.creador_id == request.user.id
            or tarea.proyecto.integrantes.filter(pk=request.user.pk).exists()
            ))
        )
    ) or (
        rol == "profesor" and (
            (tarea.proyecto_id is not None and profesor_autorizado(request.user, tarea.proyecto))
            or (tarea.proyecto_id is None and AsignacionTarea.objects.filter(tarea=tarea, alumno=entrega.alumno, profesor=request.user).exists())
        )
    )
    if not autorizado:
        raise Http404
    try:
        filename = entrega.archivo.name.rsplit("/", 1)[-1]
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        can_preview = content_type in {"application/pdf", "image/png", "image/jpeg"}
        inline = request.GET.get("inline") == "1" and can_preview
        response = FileResponse(
            entrega.archivo.open("rb"),
            as_attachment=not inline,
            filename=filename,
            content_type=content_type,
        )
    except (FileNotFoundError, ValueError):
        raise Http404
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def lista_tareas(request):
    if _rol(request.user) == "profesor":
        return redirect("core:profesor")
    return redirect("core:alumno")
