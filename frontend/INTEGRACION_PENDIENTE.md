# Integraciones y límites actuales

## Perfil y seguridad

- `GET/PATCH /usuarios/api/perfil/` devuelve datos de la cuenta autenticada y permite registrar IPP, GAO o TP una sola vez. La API y el modelo bloquean cambios posteriores.
- `POST /usuarios/api/cambiar-contrasena/` verifica la contraseña actual, la confirmación y los validadores configurados en Django. Guarda con `set_password` y mantiene la sesión con `update_session_auth_hash`.
- `backend/usuarios/migrations/0004_perfilusuario_especialidad.py` está generada y revisada, pero no aplicada. Debe aprobarse y aplicarse en cada entorno después de respaldo y revisión.
- Las relaciones de perfil, archivos, documentos, tareas, entregas y devoluciones que preservan historial usan `PROTECT`. Las migraciones aditivas correspondientes siguen a las hojas actuales: usuarios 0005, archivos 0006, documentos 0003–0004, tareas 0005–0006 y proyectos 0007–0008. No se aplicaron; antes de hacerlo hay que verificar el historial de cada base de datos.

## Revisiones docentes

- Las entregas rechazadas conservan estado y motivo en su fila; una corrección crea una fila nueva enlazada al intento anterior. El docente solo puede revisar el intento vigente del proyecto que tiene asignado.
- `PATCH /documentos/api/<id>/estado-revision/` permite al docente asignado marcar `pendiente`, `en_revision` o `revisado`. El alumno consulta el estado en el serializador del documento; editar contenido de proyecto devuelve el estado a `pendiente` y una evaluación docente lo marca `revisado`.
- El panel docente cuenta entregas vigentes `entregada`/`en_revision` y documentos con estado `pendiente`/`en_revision`; las revisiones cerradas quedan fuera de la cola.

## Archivos

- La API de archivos es privada y filtra por propietario o pertenencia/asignación al proyecto. Valida extensión y tamaño, almacena fuera de archivos públicos y autoriza las descargas.
- El frontend permite crear carpetas de primer nivel, filtrar, mover y eliminar archivos propios. La API no ofrece eliminar carpetas ni carpetas anidadas.
- El indicador de espacio suma los tamaños reales de los archivos cargados en la vista actual y conserva el texto «en esta vista». La barra de color decorativa no se usa.

## Tareas y entregas

- La prioridad se recalcula con la fecha límite en la zona horaria de Django: baja desde 14 días, media entre 8 y 13, alta de 0 a 7 y vencida al pasar la fecha si no hay entrega válida ni tarea finalizada.
- El alumno consulta `GET /tareas/api/<id>/entregas/`. La interfaz compara la fecha real de cada intento con la fecha límite. Las entregas rechazadas se muestran con el motivo y permiten una nueva entrega; cada archivo y fecha anterior se conserva.
- La devolución docente usa `POST /tareas/api/<tarea_id>/entregas/<entrega_id>/revision/`; el motivo es obligatorio al rechazar. El reintento se permite solo cuando el último intento fue rechazado; no existe una API para que el alumno modifique o borre una entrega ya registrada.

## Proyectos y documentos

- Los proyectos, tareas, archivos y documentos se consultan con APIs que filtran por integrante o docente asignado. La vista muestra tarjetas compactas, tablero independiente y recursos del proyecto seleccionado.
- Ambos editores usan el formato `eduflow.rich-text` en el campo `contenido`; la API existente conserva versiones, permisos y conflictos HTTP 409. El docente puede revisar/evaluar documentos asignados y no editar el contenido de alumnos.
- Los estados documentales son explícitos y no se calculan desde `DevolucionDocente`; las devoluciones existentes continúan siendo historial académico.

## Migración requerida por la etapa de entregas y revisiones

Las migraciones las gestiona otra persona; no se generaron ni aplicaron en esta etapa. El cambio de esquema requerido es:

- `tareas.Entrega`: agregar `entrega_anterior` como `OneToOneField` nullable hacia `self`, `on_delete=PROTECT`, `related_name="siguiente_entrega"`; agregar `devolucion` como `TextField(blank=True, default="")`; eliminar la restricción única `una_entrega_por_alumno_tarea` para permitir intentos sucesivos.
- `documentos.Documento`: agregar `estado_revision` como `CharField(max_length=20, choices=pendiente/en_revision/revisado, default="pendiente")`.
- La migración de datos debe conservar todas las entregas existentes como intentos iniciales (`entrega_anterior=NULL`) y el motivo vacío. Para documentos existentes, puede marcar `revisado` cuando `evaluado_por` ya está registrado y `pendiente` en los demás casos; no debe borrar devoluciones ni documentos.
- La app verifica que el intento anterior pertenezca a la misma tarea y esté rechazado. Esa regla y la unicidad de sucesor deben probarse también en el motor productivo.

## Pruebas y dependencias del entorno

- Los tests de backend pueden correr en SQLite en memoria. En este entorno hubo que omitir el middleware WhiteNoise solo para la corrida de tests porque el paquete no está instalado en el `venv`; no se cambió la configuración de despliegue.
- La migración de especialidad y el cambio de esquema de entregas/revisión quedan pendientes. No se aplicó ninguna migración a la base de datos configurada.
