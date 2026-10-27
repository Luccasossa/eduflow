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
