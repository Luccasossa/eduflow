import os
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_GET, require_http_methods

from proyectos.models import Proyecto
from proyectos.permissions import profesor_autorizado
from .models import Archivo, Carpeta

EXTENSIONES = {".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".txt", ".csv"}
TIPOS = {
    ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text", ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation", ".txt": "text/plain", ".csv": "text/csv",
}
MAX_UPLOAD_SIZE = int(os.environ.get("EDUFLOW_MAX_UPLOAD_SIZE", 15 * 1024 * 1024))


def _rol(usuario):
    return getattr(getattr(usuario, "perfil", None), "rol", None)


def _puede_ver(usuario, archivo):
    if _rol(usuario) == "profesor":
        return (archivo.proyecto_id is not None and profesor_autorizado(usuario, archivo.proyecto)) or archivo.propietario_id == usuario.id
    if archivo.proyecto_id:
        return archivo.propietario_id == usuario.id or archivo.proyecto.creador_id == usuario.id or archivo.proyecto.integrantes.filter(pk=usuario.pk).exists()
    return archivo.propietario_id == usuario.id


def _serializar(archivo):
    nombre = archivo.nombre_original or os.path.basename(archivo.archivo.name)
    return {
        "id": archivo.id, "nombre": nombre, "tipo": archivo.tipo,
        "tamano": archivo.tamano, "fecha_subida": archivo.fecha_subida.isoformat(),
        "proyecto_id": archivo.proyecto_id, "carpeta": archivo.carpeta_id,
        "descarga": f"/archivos/api/{archivo.id}/descargar/",
    }


def _validar_contenido(upload, extension):
    head = upload.read(16)
    upload.seek(0)
    if extension == ".pdf":
        return head.startswith(b"%PDF-")
    if extension in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        if not zipfile.is_zipfile(upload):
            upload.seek(0)
            return False
        upload.seek(0)
        try:
            with zipfile.ZipFile(upload) as package:
                names = set(package.namelist())
                if extension == ".docx":
                    return "word/document.xml" in names
                if extension == ".xlsx":
                    return "xl/workbook.xml" in names
                if extension == ".pptx":
                    return "ppt/presentation.xml" in names
                return "mimetype" in names and ("content.xml" in names or any(name.endswith("/content.xml") for name in names))
        except (zipfile.BadZipFile, OSError):
            return False
        finally:
            upload.seek(0)
    try:
        for chunk in upload.chunks():
            if b"\x00" in chunk:
                return False
            chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    finally:
        upload.seek(0)
    return True


@login_required
@require_GET
def lista_archivos(request):
    rol = _rol(request.user)
    if rol == "profesor":
        return redirect("core:profesor")
    if rol == "alumno":
        return redirect("core:alumno")
    return HttpResponseForbidden("Tu cuenta no tiene un rol habilitado.")


@login_required
@require_http_methods(["GET", "POST"])
def api_archivos(request):
    rol = _rol(request.user)
    if rol not in ("alumno", "profesor"):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    if request.method == "GET":
        qs = Archivo.objects.select_related("proyecto", "carpeta", "propietario")
        if rol == "alumno":
            from django.db.models import Q
            qs = qs.filter(Q(propietario=request.user) | Q(proyecto__integrantes=request.user) | Q(proyecto__creador=request.user)).distinct()
        else:
            from django.db.models import Q
            qs = qs.filter(Q(proyecto__profesores=request.user) | Q(propietario=request.user))
            if request.user.is_superuser:
                qs = Archivo.objects.select_related("proyecto", "carpeta", "propietario")
        proyecto_id = request.GET.get("proyecto")
        if proyecto_id:
            if not proyecto_id.isdigit():
                return JsonResponse({"error": "El proyecto indicado no es válido."}, status=400)
            qs = qs.filter(proyecto_id=proyecto_id)
        carpeta_id = request.GET.get("carpeta")
        if carpeta_id:
            if not carpeta_id.isdigit():
                return JsonResponse({"error": "La carpeta indicada no es válida."}, status=400)
            qs = qs.filter(carpeta_id=carpeta_id)
        return JsonResponse({"archivos": [_serializar(f) for f in qs.order_by("-fecha_subida")]})

    upload = request.FILES.get("archivo")
    if not upload:
        return JsonResponse({"error": "Selecciona un archivo."}, status=400)
    original = os.path.basename(upload.name.replace("\\", "/"))
    if not original or len(original) > 255:
        return JsonResponse({"error": "El nombre del archivo debe tener entre 1 y 255 caracteres."}, status=400)
    extension = os.path.splitext(original)[1].lower()
    if extension not in EXTENSIONES:
        return JsonResponse({"error": "Tipo de archivo no permitido."}, status=400)
    if upload.size <= 0 or upload.size > MAX_UPLOAD_SIZE:
        return JsonResponse({"error": f"El archivo debe pesar hasta {MAX_UPLOAD_SIZE // (1024 * 1024)} MB."}, status=400)
    if not _validar_contenido(upload, extension):
        return JsonResponse({"error": "El contenido no coincide con un documento válido."}, status=400)
    proyecto = None
    if request.POST.get("proyecto"):
        proyecto = get_object_or_404(Proyecto, pk=request.POST["proyecto"])
        if rol == "alumno" and not (proyecto.creador_id == request.user.id or proyecto.integrantes.filter(pk=request.user.pk).exists()):
            raise Http404
        if rol == "profesor" and not profesor_autorizado(request.user, proyecto):
            raise Http404
    carpeta = None
    if request.POST.get("carpeta"):
        carpeta = get_object_or_404(Carpeta, pk=request.POST["carpeta"], propietario=request.user)
        if proyecto and carpeta.propietario_id != request.user.id:
            return JsonResponse({"error": "La carpeta no pertenece a tu cuenta."}, status=400)
    archivo = Archivo(
        archivo=upload, nombre_original=original, tipo=TIPOS[extension], tamano=upload.size,
        propietario=request.user, proyecto=proyecto, carpeta=carpeta,
    )
    archivo.save()
    return JsonResponse({"archivo": _serializar(archivo)}, status=201)


@login_required
@require_GET
def descargar_archivo(request, pk):
    archivo = get_object_or_404(Archivo.objects.select_related("proyecto"), pk=pk)
    if not _puede_ver(request.user, archivo):
        raise Http404
    try:
        response = FileResponse(archivo.archivo.open("rb"), as_attachment=True, filename=archivo.nombre_original or os.path.basename(archivo.archivo.name), content_type=archivo.tipo)
    except (OSError, ValueError):
        raise Http404
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET", "POST"])
def api_carpetas(request):
    if _rol(request.user) not in ("alumno", "profesor"):
        return JsonResponse({"error": "Tu cuenta no tiene un rol habilitado."}, status=403)
    if request.method == "GET":
        carpetas = Carpeta.objects.filter(propietario=request.user).order_by("nombre")
        return JsonResponse({"carpetas": [{"id": c.id, "nombre": c.nombre, "padre": c.carpeta_padre_id} for c in carpetas]})
    nombre = request.POST.get("nombre", "").strip()
    padre_id = request.POST.get("padre", "")
    if not nombre or len(nombre) > 150:
        return JsonResponse({"error": "El nombre de carpeta es obligatorio (máximo 150 caracteres)."}, status=400)
    padre = None
    if padre_id:
        padre = get_object_or_404(Carpeta, pk=padre_id, propietario=request.user)
    carpeta = Carpeta.objects.create(nombre=nombre, propietario=request.user, carpeta_padre=padre)
    return JsonResponse({"carpeta": {"id": carpeta.id, "nombre": carpeta.nombre, "padre": carpeta.carpeta_padre_id}}, status=201)
