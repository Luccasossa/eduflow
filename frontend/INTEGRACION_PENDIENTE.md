# Integraciones de frontend pendientes

La interfaz conserva las rutas y los nombres de campos de las APIs existentes. Estas operaciones no se muestran como guardadas cuando el backend no ofrece soporte.

## Perfil de alumno y docente

- No existe una API de lectura/actualización de perfil ni una API de cambio de contraseña.
- Nombres, apellidos, correo y DNI se leen desde el usuario autenticado en las plantillas; en los modales permanecen de solo lectura y Guardar está deshabilitado.
- El modelo PerfilUsuario no tiene especialidad ni materias a cargo. El frontend informa esa ausencia y no inventa valores.
- Para habilitar edición hace falta una API autenticada de perfil que valide esos campos y use los mecanismos de Django para cambiar contraseñas (validación de contraseña y set_password). También debe definirse dónde se almacenarán especialidad y materias.

## Seguimiento de documentos

- El endpoint de documentos entrega calificación y retroalimentación, pero no un estado explícito de revisión.
- El resumen muestra como “sin devolución registrada” los documentos sin calificación ni retroalimentación. Es el indicador que permiten los datos actuales; no afirma que un docente haya confirmado que están pendientes.
- Para identificar pendientes sin ambigüedad, el backend debe exponer un estado de revisión o una fecha/autor de revisión.

## Carpetas de archivos de cátedra

- La API actual permite crear carpetas personales y asociarles archivos; el frontend filtra los archivos por carpeta y conserva el enlace de descarga autorizado.
- El modelo actual solo permite carpetas de primer nivel y no expone operaciones para mover, renombrar o borrar carpetas/archivos. La interfaz no presenta jerarquías ni esas acciones.

## Proyectos y tareas

- La API de proyectos expone integrantes, fecha, progreso y tareas; el tipo individual/grupal se deriva del número de integrantes.
- La API no define un estado “activo” del proyecto; el resumen considera activos los proyectos con progreso menor a 100%.
- La prioridad de las tareas se calcula en el navegador con la zona horaria activa de Django y se refresca al cambiar el día; no se envía una prioridad modificada al backend.
- La vista del alumno consulta documentos y archivos con el filtro de proyecto existente y utiliza el ID del proyecto al crear documentos o subir archivos. No requiere endpoints adicionales.
