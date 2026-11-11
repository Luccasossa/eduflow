def rol(usuario):
    return getattr(getattr(usuario, "perfil", None), "rol", None)


def profesor_autorizado(usuario, proyecto):
    return bool(
        usuario.is_authenticated
        and rol(usuario) == "profesor"
        and (usuario.is_superuser or proyecto.profesores.filter(pk=usuario.pk).exists())
    )


def alumno_integrante(usuario, proyecto):
    return bool(
        usuario.is_authenticated
        and rol(usuario) == "alumno"
        and (proyecto.creador_id == usuario.pk or proyecto.integrantes.filter(pk=usuario.pk).exists())
    )


def profesor_supervisa_alumno(usuario, alumno):
    """A professor can see a student's common tasks when they share a supervised project."""
    if not usuario.is_authenticated or rol(usuario) != "profesor":
        return False
    if usuario.is_superuser:
        return True
    from django.db.models import Q
    from .models import Proyecto
    return Proyecto.objects.filter(profesores=usuario).filter(
        Q(creador=alumno) | Q(integrantes=alumno)
    ).exists()
