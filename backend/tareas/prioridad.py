from django.utils.timezone import localdate

from .models import Tarea


def prioridad_para(fecha):
    if not fecha:
        return "media"
    dias = (fecha - localdate()).days
    return "baja" if dias >= 14 else "media" if dias >= 8 else "alta"


def sincronizar_prioridades(tareas):
    pendientes = []
    for tarea in tareas:
        prioridad = prioridad_para(tarea.fecha_vencimiento)
        if tarea.prioridad != prioridad:
            tarea.prioridad = prioridad
            pendientes.append(tarea)
    if pendientes:
        Tarea.objects.bulk_update(pendientes, ("prioridad",))
