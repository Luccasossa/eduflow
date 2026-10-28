import mimetypes
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from proyectos.models import Proyecto
from proyectos.permissions import alumno_integrante, profesor_autorizado, rol as rol_usuario
from tareas.models import Tarea

from .models import Archivo, Carpeta
from .validators import MAX_FILE_SIZE, validar_archivo


# Kept as a view-level setting for deployments and compatibility with checks
# that override the limit without modifying the shared model validator.
MAX_UPLOAD_SIZE = MAX_FILE_SIZE


def _project_or_404(usuario, proyecto_id):
    if not str(proyecto_id).isdigit():
        raise Http404
    proyecto = get_object_or_404(Proyecto, pk=proyecto_id)
    if not (alumno_integrante(usuario, proyecto) or profesor_autorizado(usuario, proyecto)):
        raise Http404
    return proyecto


def _authorized_projects(usuario):
    if rol_usuario(usuario) == "profesor":
        projects = Proyecto.objects.filter(profesores=usuario)
        if usuario.is_superuser:
            projects = Proyecto.objects.all()
        return projects
    if rol_usuario(usuario) == "alumno":
        return Proyecto.objects.filter(Q(creador=usuario) | Q(integrantes=usuario)).distinct()
    return Proyecto.objects.none()


def _authorized_tasks(usuario, projects):
    tasks = Tarea.objects.filter(proyecto__in=projects)
    if rol_usuario(usuario) == "alumno":
        tasks = tasks | Tarea.objects.filter(creador=usuario, proyecto__isnull=True)
    return tasks.distinct()


def _has_academic_role(usuario):
    return rol_usuario(usuario) in ("alumno", "profesor")


def _file_queryset(usuario):
    projects = _authorized_projects(usuario)
    tasks = _authorized_tasks(usuario, projects)
    task_file_access = (
        Q(tarea__in=tasks, proyecto__isnull=True)
        | Q(tarea__in=tasks, proyecto_id=F("tarea__proyecto_id"))
    )
    return Archivo.objects.filter(
        Q(propietario=usuario) | Q(proyecto__in=projects) | task_file_access
    ).select_related("proyecto", "carpeta", "tarea").distinct()


def _serialize_file(archivo):
    return {
        "id": archivo.pk,
        "nombre": archivo.nombre_original or archivo.archivo.name.rsplit("/", 1)[-1],
        "tamano": archivo.tamano,
        "fecha_subida": archivo.fecha_subida.isoformat(),
        "proyecto_id": archivo.proyecto_id or (archivo.tarea.proyecto_id if archivo.tarea_id else None),
        "descarga": reverse("descargar_archivo", args=[archivo.pk]),
    }


def _parse_optional_id(value, label):
    if value in (None, ""):
        return None
    if not str(value).isdigit() or int(value) < 1:
        raise ValueError(f"El identificador de {label} no es válido.")
    return int(value)


def _clean_uploaded_file(uploaded):
    if uploaded.size > MAX_UPLOAD_SIZE:
        raise ValidationError("El archivo no puede superar los 10 MB.")
    validar_archivo(uploaded)


def _save_uploaded_file(usuario, uploaded, *, carpeta=None, proyecto=None, tarea=None):
    _clean_uploaded_file(uploaded)
    original_name = uploaded.name.replace("\\", "/").rsplit("/", 1)[-1]
    tipo = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    archivo = Archivo(
        archivo=uploaded,
        nombre_original=original_name[:255],
        tamano=uploaded.size,
        tipo=tipo[:100],
        propietario=usuario,
        carpeta=carpeta,
        proyecto=proyecto,
        tarea=tarea,
    )
    archivo.save()
    return archivo


@login_required
@require_http_methods(["GET", "POST"])
def api_archivos(request):
    if not _has_academic_role(request.user):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    if request.method == "GET":
        archivos = _file_queryset(request.user)
        try:
            proyecto_id = _parse_optional_id(request.GET.get("proyecto"), "proyecto")
            carpeta_id = _parse_optional_id(request.GET.get("carpeta"), "carpeta")
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        if proyecto_id is not None:
            try:
                proyecto = _project_or_404(request.user, proyecto_id)
            except Http404:
                raise
            archivos = archivos.filter(Q(proyecto=proyecto) | Q(tarea__proyecto=proyecto))
        if carpeta_id is not None:
            carpeta = get_object_or_404(Carpeta, pk=carpeta_id, propietario=request.user)
            archivos = archivos.filter(carpeta=carpeta)

        return JsonResponse({
            "archivos": [_serialize_file(archivo) for archivo in archivos.order_by("-fecha_subida", "-pk")]
        })

    uploaded = request.FILES.get("archivo")
    if uploaded is None:
        return JsonResponse({"error": "Debés seleccionar un archivo."}, status=400)

    try:
        carpeta_id = _parse_optional_id(request.POST.get("carpeta"), "carpeta")
        proyecto_id = _parse_optional_id(request.POST.get("proyecto"), "proyecto")
        tarea_id = _parse_optional_id(request.POST.get("tarea"), "tarea")
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    carpeta = None
    if carpeta_id is not None:
        carpeta = get_object_or_404(Carpeta, pk=carpeta_id, propietario=request.user)

    proyecto = _project_or_404(request.user, proyecto_id) if proyecto_id is not None else None
    tarea = None
    if tarea_id is not None:
        tarea = get_object_or_404(Tarea.objects.select_related("proyecto"), pk=tarea_id)
        if tarea.proyecto_id:
            if proyecto_id is not None and proyecto_id != tarea.proyecto_id:
                return JsonResponse({"error": "La tarea no pertenece al proyecto indicado."}, status=400)
            proyecto = _project_or_404(request.user, tarea.proyecto_id)
        elif rol_usuario(request.user) != "alumno" or tarea.creador_id != request.user.pk:
            raise Http404

    try:
        archivo = _save_uploaded_file(
            request.user, uploaded, carpeta=carpeta, proyecto=proyecto, tarea=tarea
        )
    except ValidationError as exc:
        message = "; ".join(exc.messages)
        return JsonResponse({"error": message}, status=400)

    return JsonResponse({"archivo": _serialize_file(archivo)}, status=201)


@login_required
@require_http_methods(["GET", "POST"])
def api_carpetas(request):
    if not _has_academic_role(request.user):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    if request.method == "GET":
        return JsonResponse({
            "carpetas": [
                {"id": carpeta.pk, "nombre": carpeta.nombre}
                for carpeta in Carpeta.objects.filter(propietario=request.user).order_by("nombre", "pk")
            ]
        })

    nombre = request.POST.get("nombre", "")
    if not isinstance(nombre, str):
        return JsonResponse({"error": "El nombre de la carpeta no es válido."}, status=400)
    nombre = nombre.strip()
    if not nombre or len(nombre) > 150 or re.search(r"[\\/\x00-\x1f]", nombre):
        return JsonResponse({"error": "El nombre debe tener entre 1 y 150 caracteres y no incluir separadores."}, status=400)
    carpeta = Carpeta.objects.create(nombre=nombre, propietario=request.user)
    return JsonResponse({"carpeta": {"id": carpeta.pk, "nombre": carpeta.nombre}}, status=201)


@login_required
@require_GET
def descargar_archivo(request, pk):
    if not _has_academic_role(request.user):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    archivo = get_object_or_404(_file_queryset(request.user), pk=pk)
    if not archivo.archivo:
        raise Http404
    try:
        stream = archivo.archivo.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404

    nombre = archivo.nombre_original or "archivo"
    response = FileResponse(
        stream,
        as_attachment=True,
        filename=nombre,
        content_type=archivo.tipo or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "sandbox"
    return response


@login_required
def lista_archivos(request):
    if not _has_academic_role(request.user):
        return HttpResponseForbidden("Tu cuenta no tiene un rol habilitado.")
    return render(request, "archivos/lista.html", {
        "archivos": _file_queryset(request.user),
        "carpetas": Carpeta.objects.filter(propietario=request.user),
    })


@login_required
@require_http_methods(["POST"])
def subir_archivo(request):
    if not _has_academic_role(request.user):
        return HttpResponseForbidden("Tu cuenta no tiene un rol habilitado.")
    uploaded = request.FILES.get("archivo")
    if uploaded is None:
        return redirect("lista_archivos")
    try:
        _save_uploaded_file(request.user, uploaded)
    except ValidationError:
        return redirect("lista_archivos")
    return redirect("lista_archivos")
