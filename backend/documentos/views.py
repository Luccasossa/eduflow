import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django import forms
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_http_methods
from django.conf import settings

from proyectos.models import Proyecto
from proyectos.models import DevolucionDocente
from proyectos.permissions import profesor_autorizado
from .models import Documento


def _rol(usuario):
    return getattr(getattr(usuario, "perfil", None), "rol", None)


def _json_body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _es_colaborador(documento, usuario):
    if documento.proyecto_id:
        return documento.proyecto.creador_id == usuario.id or documento.proyecto.integrantes.filter(pk=usuario.pk).exists()
    return documento.creador_id == usuario.id or documento.colaboradores.filter(pk=usuario.pk).exists()


def _serializar(documento, usuario=None):
    es_autor = bool(usuario and usuario.id == documento.creador_id)
    colaboracion_alumno = bool(
        usuario and _rol(usuario) == "alumno" and documento.proyecto_id
        and _rol(documento.creador) == "alumno" and _es_colaborador(documento, usuario)
    )
    return {
        "id": documento.id, "titulo": documento.titulo, "contenido": documento.contenido,
        "creador": documento.creador.get_full_name() or documento.creador.dni,
        "creador_id": documento.creador_id,
        "colaboradores": [{"id": u.id, "nombre": u.get_full_name() or u.dni} for u in documento.colaboradores.all()],
        "proyecto_id": documento.proyecto_id, "proyecto": documento.proyecto.nombre if documento.proyecto_id else "",
        "version": documento.version, "fecha_actualizacion": documento.fecha_actualizacion.isoformat(),
        "calificacion": str(documento.calificacion) if documento.calificacion is not None else "",
        "retroalimentacion": documento.retroalimentacion,
        "puede_editar": es_autor or colaboracion_alumno,
        "puede_eliminar": es_autor,
    }


def _visible_a(documento, usuario):
    return (documento.proyecto_id and profesor_autorizado(usuario, documento.proyecto)) or (_rol(usuario) == "profesor" and documento.proyecto_id is None and documento.creador_id == usuario.id) or (_rol(usuario) == "alumno" and _es_colaborador(documento, usuario))


@login_required
@require_GET
def lista_documentos(request):
    rol = _rol(request.user)
    if rol == "profesor":
        return redirect("core:profesor")
    if rol == "alumno":
        return redirect("core:alumno")
    return HttpResponseForbidden("Tu cuenta no tiene un rol habilitado.")


@login_required
@require_http_methods(["GET", "POST"])
def api_documentos(request):
    rol = _rol(request.user)
    if rol not in ("alumno", "profesor"):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    if request.method == "GET":
        documentos = Documento.objects.select_related("creador", "proyecto").prefetch_related("colaboradores")
        if rol == "alumno":
            from django.db.models import Q
            documentos = documentos.filter(
                Q(proyecto__isnull=True, creador=request.user)
                | Q(proyecto__isnull=True, colaboradores=request.user)
                | Q(proyecto__creador=request.user)
                | Q(proyecto__integrantes=request.user)
            ).distinct()
        else:
            from django.db.models import Q
            documentos = documentos.filter(
                Q(proyecto__profesores=request.user)
                | Q(proyecto__isnull=True, creador=request.user)
            )
            if request.user.is_superuser:
                documentos = Documento.objects.select_related("creador", "proyecto").prefetch_related("colaboradores")
        if request.GET.get("proyecto"):
            if not request.GET["proyecto"].isdigit():
                return JsonResponse({"error": "El proyecto indicado no es válido."}, status=400)
            documentos = documentos.filter(proyecto_id=request.GET["proyecto"])
        return JsonResponse({"documentos": [_serializar(d, request.user) for d in documentos.order_by("-fecha_actualizacion")]})
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    titulo = data.get("titulo", "")
    contenido = data.get("contenido", "")
    if not isinstance(titulo, str) or not titulo.strip() or len(titulo.strip()) > 200:
        return JsonResponse({"error": "El título es obligatorio y admite hasta 200 caracteres."}, status=400)
    titulo = titulo.strip()
    if not isinstance(contenido, str) or len(contenido) > 1_000_000:
        return JsonResponse({"error": "El contenido debe ser texto y no superar 1 MB."}, status=400)
    proyecto = None
    if data.get("proyecto") not in (None, ""):
        proyecto_id = data["proyecto"]
        if isinstance(proyecto_id, bool) or not (
            isinstance(proyecto_id, int)
            or (isinstance(proyecto_id, str) and proyecto_id.isdigit())
        ):
            return JsonResponse({"error": "El proyecto indicado no es valido."}, status=400)
        proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
        if rol == "profesor" and not profesor_autorizado(request.user, proyecto):
            raise Http404
        if rol == "alumno" and proyecto.creador_id != request.user.id and not proyecto.integrantes.filter(pk=request.user.pk).exists():
            raise Http404
    with transaction.atomic():
        documento = Documento.objects.create(titulo=titulo, contenido=contenido, creador=request.user, proyecto=proyecto)
        if proyecto:
            documento.colaboradores.add(*proyecto.integrantes.exclude(pk=request.user.pk))
    return JsonResponse({"documento": _serializar(documento, request.user)}, status=201)


@login_required
@require_http_methods(["GET", "PATCH", "DELETE"])
def api_documento(request, pk):
    documento = get_object_or_404(Documento.objects.select_related("creador", "proyecto").prefetch_related("colaboradores"), pk=pk)
    rol = _rol(request.user)
    if not _visible_a(documento, request.user):
        raise Http404
    if request.method != "GET":
        if documento.creador_id != request.user.id and not (
            rol == "alumno" and documento.proyecto_id and _rol(documento.creador) == "alumno"
        ):
            return JsonResponse({"error": "Solo el autor o un colaborador autorizado puede modificar este documento."}, status=403)
    if request.method == "GET":
        return JsonResponse({"documento": _serializar(documento, request.user)})
    if request.method == "DELETE":
        if documento.creador_id != request.user.id:
            return JsonResponse({"error": "Solo quien creó el documento puede eliminarlo."}, status=403)
        documento.delete()
        return JsonResponse({"eliminado": True})
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON válido."}, status=400)
    if "version" not in data:
        return JsonResponse({"error": "Envía la versión que estás editando para detectar conflictos."}, status=400)
    try:
        version_input = data["version"]
        if isinstance(version_input, bool) or not (
            isinstance(version_input, int)
            or (isinstance(version_input, str) and version_input.isdigit())
        ):
            raise ValueError
        version = int(version_input)
        if version < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "La versión del documento no es válida."}, status=400)
    with transaction.atomic():
        actual = Documento.objects.select_for_update().select_related("creador", "proyecto").get(pk=pk)
        if not _visible_a(actual, request.user):
            raise Http404
        if actual.version != version:
            return JsonResponse({"error": "El documento cambió desde que lo abriste. Recarga la versión actual antes de guardar.", "conflicto": True, "documento": _serializar(actual, request.user)}, status=409)
        if actual.creador_id != request.user.id and actual.proyecto_id is None:
            # Personal collaborators can read; only the owner edits private documents.
            return JsonResponse({"error": "Solo el propietario puede editar este documento."}, status=403)
        titulo = data.get("titulo", actual.titulo)
        contenido = data.get("contenido", actual.contenido)
        if not isinstance(titulo, str) or not titulo.strip() or len(titulo.strip()) > 200:
            return JsonResponse({"error": "El título es obligatorio y admite hasta 200 caracteres."}, status=400)
        if not isinstance(contenido, str) or len(contenido) > 1_000_000:
            return JsonResponse({"error": "El contenido debe ser texto y no superar 1 MB."}, status=400)
        actual.titulo = titulo.strip()
        actual.contenido = contenido
        actual.version += 1
        actual.save(update_fields=("titulo", "contenido", "version", "fecha_actualizacion"))
    return JsonResponse({"documento": _serializar(actual, request.user)})


@login_required
@require_http_methods(["PATCH"])
def api_evaluar_documento(request, pk):
    if _rol(request.user) != "profesor":
        return JsonResponse({"error": "Solo los profesores pueden dejar retroalimentaci\u00f3n."}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": "El cuerpo de la solicitud debe ser JSON v\u00e1lido."}, status=400)

    with transaction.atomic():
        documento = get_object_or_404(
            Documento.objects.select_for_update().select_related("proyecto"),
            pk=pk,
            proyecto__isnull=False,
        )
        if not profesor_autorizado(request.user, documento.proyecto):
            raise Http404

        feedback = data.get("retroalimentacion", documento.retroalimentacion)
        if not isinstance(feedback, str) or len(feedback) > 20000:
            return JsonResponse({"error": "La retroalimentaci\u00f3n debe ser texto de hasta 20.000 caracteres."}, status=400)
        documento.retroalimentacion = feedback.strip()
        if "calificacion" in data:
            try:
                documento.calificacion = forms.DecimalField(
                    max_digits=5,
                    decimal_places=2,
                    min_value=0,
                    max_value=settings.EDUFLOW_GRADE_MAX,
                ).clean(data["calificacion"])
            except (ValidationError, TypeError):
                return JsonResponse({"error": "La calificaci\u00f3n debe ser un n\u00famero v\u00e1lido igual o mayor que cero."}, status=400)
        if not documento.retroalimentacion.strip() and "calificacion" not in data:
            return JsonResponse({"error": "La devoluci\u00f3n debe incluir un comentario o una calificaci\u00f3n."}, status=400)

        nota_de_esta_devolucion = documento.calificacion if "calificacion" in data else None
        devolucion = DevolucionDocente(
            proyecto=documento.proyecto,
            documento=documento,
            autor=request.user,
            comentario=documento.retroalimentacion,
            calificacion=nota_de_esta_devolucion,
        )
        try:
            devolucion.full_clean()
        except ValidationError:
            return JsonResponse({"error": "La devoluci\u00f3n no es v\u00e1lida."}, status=400)
        devolucion.save()
        documento.evaluado_por = request.user
        documento.save(update_fields=("retroalimentacion", "calificacion", "evaluado_por"))

    return JsonResponse({
        "documento": _serializar(documento, request.user),
        "retroalimentacion": documento.retroalimentacion,
        "calificacion": str(documento.calificacion or ""),
    })
