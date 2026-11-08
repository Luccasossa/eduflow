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
from .models import Entrega, Tarea
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
        "calificacion": str(tarea.calificacion) if tarea.calificacion is not None else "",
        "retroalimentacion": tarea.retroalimentacion,
        "archivos_adjuntos": [
            {"id": f.pk, "nombre": f.nombre_original, "abrir": f"/archivos/api/{f.pk}/descargar/?inline=1", "descarga": f"/archivos/api/{f.pk}/descargar/", "puede_quitar": bool(usuario and f.propietario_id == usuario.pk)}
            for f in tarea.archivos_adjuntos.all()
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
            tareas = Tarea.objects.filter(creador=request.user, proyecto__isnull=True)
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
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_tarea(request, pk):
    tarea = _tarea_autorizada(request, pk)
    if request.method == "GET":
        return JsonResponse({"tarea": _serializar(tarea, request.user)})
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
        if not already_attached:
            from core.models import Actividad
            Actividad.objects.create(usuario=request.user, descripcion=f"Adjuntaste {archivo.nombre_original} a la tarea {tarea.titulo}.", tipo="adjunto", tarea=tarea, archivo=archivo)
        return JsonResponse({"adjuntado": True})
    tarea.archivos_adjuntos.remove(archivo)
    return JsonResponse({"quitado": True})


def _serializar_entrega(entrega):
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
    }


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
            (tarea.proyecto_id is None and entrega.alumno_id == request.user.id)
            or (tarea.proyecto_id is not None and (
            tarea.proyecto.creador_id == request.user.id
            or tarea.proyecto.integrantes.filter(pk=request.user.pk).exists()
            ))
        )
    ) or (
        rol == "profesor" and tarea.proyecto_id is not None
        and profesor_autorizado(request.user, tarea.proyecto)
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
