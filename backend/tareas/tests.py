import json
import tempfile
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from proyectos.models import Proyecto
from usuarios.models import PerfilUsuario
from .models import AsignacionTarea, CorreccionEntrega, Entrega, Tarea

Usuario = get_user_model()


class TablerosTests(TestCase):
    def crear_usuario(self, dni, rol="alumno"):
        usuario = Usuario.objects.create_user(
            dni=dni,
            password="ClaveSegura_2026!",
            first_name=f"Usuario {dni}",
            email=f"{dni}@example.test",
        )
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        return usuario

    def json_post(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        self._settings = override_settings(PRIVATE_MEDIA_ROOT=self._media.name)
        self._settings.enable()
        self.addCleanup(self._settings.disable)
        storage = Entrega._meta.get_field("archivo").storage
        previous_location = storage.location
        storage.location = self._media.name
        self.addCleanup(setattr, storage, "location", previous_location)
        self.alumno = self.crear_usuario("40100001")
        self.companero = self.crear_usuario("40100002")
        self.ajeno = self.crear_usuario("40100003")
        self.profesor = self.crear_usuario("40100004", "profesor")

    def test_alumno_crea_tarea_personal_vinculada_a_su_cuenta(self):
        self.client.force_login(self.alumno)
        response = self.json_post(reverse("api_tareas"), {
            "titulo": "Repasar SQL",
            "descripcion": "Normalización y consultas",
            "fecha_vencimiento": "2026-11-02",
            "prioridad": "alta",
        })
        self.assertEqual(response.status_code, 201)
        tarea = Tarea.objects.get()
        self.assertEqual(tarea.creador, self.alumno)
        self.assertIsNone(tarea.proyecto)
        self.assertEqual(tarea.fecha_vencimiento.isoformat(), "2026-11-02")

    def test_tarea_creada_por_alumno_aparece_en_lista_y_detalle(self):
        self.client.force_login(self.alumno)
        created = self.json_post(reverse("api_tareas"), {
            "titulo": "Lectura de historia",
            "descripcion": "Preparar el resumen del capítulo.",
        })
        self.assertEqual(created.status_code, 201, created.content)
        task_id = created.json()["tarea"]["id"]

        listing = self.client.get(reverse("api_tareas"))
        self.assertEqual(listing.status_code, 200)
        self.assertEqual([task["id"] for task in listing.json()["tareas"]], [task_id])

        detail = self.client.get(reverse("api_tarea", args=[task_id]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["tarea"]["titulo"], "Lectura de historia")
        self.assertEqual(detail.json()["tarea"]["descripcion"], "Preparar el resumen del capítulo.")

    def test_edita_estado_prioridad_fecha_y_filtros(self):
        tarea = Tarea.objects.create(creador=self.alumno, titulo="Original")
        self.client.force_login(self.alumno)
        response = self.client.patch(
            reverse("api_tarea", args=[tarea.id]),
            data=json.dumps({"titulo": "Actualizada", "estado": "en_progreso", "prioridad": "baja", "fecha_vencimiento": "2026-11-05"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        tarea.refresh_from_db()
        self.assertEqual(tarea.titulo, "Actualizada")
        self.assertEqual(tarea.estado, "en_progreso")
        expected = "baja" if (tarea.fecha_vencimiento - timezone.localdate()).days > 20 else "media" if (tarea.fecha_vencimiento - timezone.localdate()).days >= 5 else "alta"
        self.assertEqual(tarea.prioridad, expected)
        self.assertEqual(tarea.fecha_vencimiento.isoformat(), "2026-11-05")
        response = self.client.get(reverse("api_tareas") + f"?estado=en_progreso&prioridad={expected}&desde=2026-11-01&hasta=2026-11-30")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["tareas"]], [tarea.id])

    def test_prioridad_automatica_en_los_limites_requeridos(self):
        self.client.force_login(self.alumno)
        today = timezone.localdate()
        for days, expected in ((20, "baja"), (14, "baja"), (13, "media"), (8, "media"), (7, "alta"), (0, "alta"), (-1, "alta")):
            response = self.json_post(reverse("api_tareas"), {
                "titulo": f"Vencimiento {days}",
                "fecha_vencimiento": (today + timedelta(days=days)).isoformat(),
                "prioridad": "baja",
            })
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()["tarea"]["prioridad"], expected, f"{days} días")

    def test_devolucion_crea_notificacion_persistente_sin_duplicar_reintentos(self):
        from core.models import Notificacion
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe final")
        url = reverse("api_evaluacion_individual", args=[tarea.pk, self.alumno.pk])
        self.client.force_login(self.profesor)
        payload = json.dumps({"calificacion": "9.00", "comentario": "Muy buen trabajo."})
        first = self.client.post(url, data=payload, content_type="application/json")
        retry = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.json()["sin_cambios"])
        notice = Notificacion.objects.get(usuario=self.alumno, tarea=tarea)
        self.assertEqual(notice.tipo, "calificacion")
        self.assertIn("Nota: 9.00", notice.mensaje)
        self.client.force_login(self.alumno)
        response = self.client.get(reverse("core:api_notificaciones"))
        self.assertEqual(response.json()["no_leidas"], 1)
        self.assertEqual(response.json()["notificaciones"][0]["url"], f"/tareas/api/{tarea.pk}/")

    def test_elimina_tarea_propia(self):
        tarea = Tarea.objects.create(creador=self.alumno, titulo="Eliminar")
        self.client.force_login(self.alumno)
        response = self.client.delete(reverse("api_tarea", args=[tarea.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tarea.objects.filter(pk=tarea.pk).exists())

    def test_elimina_todas_tareas_personales_sin_tocar_proyectos_ni_asignaciones(self):
        propias = [Tarea.objects.create(creador=self.alumno, titulo=f"Personal {index}") for index in range(2)]
        entrega = Entrega.objects.create(
            tarea=propias[0], alumno=self.alumno,
            archivo=SimpleUploadedFile("trabajo.pdf", b"%PDF-1.4 contenido", content_type="application/pdf"),
        )
        storage, stored_path = entrega.archivo.storage, entrega.archivo.name
        self.assertTrue(storage.exists(stored_path))
        proyecto = self.crear_proyecto()
        tarea_proyecto = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Del proyecto")
        asignada = Tarea.objects.create(creador=self.profesor, titulo="Asignada")
        AsignacionTarea.objects.create(tarea=asignada, alumno=self.alumno, profesor=self.profesor)
        self.client.force_login(self.alumno)

        response = self.client.delete(reverse("api_eliminar_todas_tareas"))

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["eliminadas"], 2)
        self.assertFalse(Tarea.objects.filter(pk__in=[task.pk for task in propias]).exists())
        self.assertFalse(Entrega.objects.filter(pk=entrega.pk).exists())
        self.assertFalse(storage.exists(stored_path))
        self.assertTrue(Tarea.objects.filter(pk=tarea_proyecto.pk).exists())
        self.assertTrue(Tarea.objects.filter(pk=asignada.pk).exists())

    def test_solo_alumno_puede_eliminar_todas_sus_tareas(self):
        self.client.force_login(self.profesor)
        response = self.client.delete(reverse("api_eliminar_todas_tareas"))
        self.assertEqual(response.status_code, 403)

    def test_un_alumno_no_puede_consultar_ni_modificar_tarea_ajena(self):
        tarea = Tarea.objects.create(creador=self.alumno, titulo="Privada")
        self.client.force_login(self.ajeno)
        url = reverse("api_tarea", args=[tarea.id])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, data=json.dumps({"titulo": "Robada"}), content_type="application/json").status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 404)
        tarea.refresh_from_db()
        self.assertEqual(tarea.titulo, "Privada")

    def crear_proyecto(self):
        self.client.force_login(self.alumno)
        response = self.json_post(reverse("api_proyectos"), {
            "nombre": "Aplicación escolar",
            "descripcion": "Trabajo grupal",
            "fecha_entrega": "2026-12-01",
            "integrantes": [self.companero.id],
        })
        self.assertEqual(response.status_code, 201, response.content)
        return Proyecto.objects.get(pk=response.json()["proyecto"]["id"])

    def test_proyecto_grupal_fecha_integrantes_y_edicion_solo_por_creador(self):
        proyecto = self.crear_proyecto()
        self.assertEqual(proyecto.fecha_entrega.isoformat(), "2026-12-01")
        self.assertSetEqual(set(proyecto.integrantes.values_list("id", flat=True)), {self.alumno.id, self.companero.id})
        self.client.force_login(self.alumno)
        response = self.client.patch(
            reverse("api_proyecto", args=[proyecto.id]),
            data=json.dumps({"nombre": "Proyecto actualizado", "fecha_entrega": "2026-12-12"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nombre, "Proyecto actualizado")
        self.assertEqual(proyecto.fecha_entrega.isoformat(), "2026-12-12")
        self.client.force_login(self.companero)
        self.assertEqual(self.client.get(reverse("api_proyecto", args=[proyecto.id])).status_code, 200)
        response = self.client.patch(reverse("api_proyecto", args=[proyecto.id]), data=json.dumps({"nombre": "No autorizado"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse("api_proyecto", args=[proyecto.id])).status_code, 404)

    def test_creador_no_puede_eliminar_proyecto_con_tareas_y_se_preserva_el_historial(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Tarea asociada")
        self.client.force_login(self.alumno)
        response = self.client.delete(reverse("api_proyecto", args=[proyecto.id]))
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Proyecto.objects.filter(pk=proyecto.pk).exists())
        self.assertTrue(Tarea.objects.filter(pk=tarea.pk, proyecto=proyecto).exists())

    def test_integrante_colabora_en_tareas_y_progreso_se_persiste(self):
        proyecto = self.crear_proyecto()
        self.client.force_login(self.companero)
        response = self.json_post(reverse("api_tareas"), {
            "titulo": "Diseñar modelo",
            "proyecto": proyecto.id,
            "prioridad": "media",
        })
        self.assertEqual(response.status_code, 201, response.content)
        tarea = Tarea.objects.get(pk=response.json()["tarea"]["id"])
        self.assertEqual(tarea.proyecto, proyecto)
        self.assertEqual(tarea.creador, self.companero)
        self.client.patch(reverse("api_tarea", args=[tarea.id]), data=json.dumps({"estado": "completada"}), content_type="application/json")
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.progreso, 100)
        response = self.client.get(reverse("api_proyectos"))
        self.assertEqual(response.json()["proyectos"][0]["progreso"], 100)

    def test_usuario_ajeno_no_puede_crear_tareas_en_proyecto(self):
        proyecto = self.crear_proyecto()
        self.client.force_login(self.ajeno)
        response = self.json_post(reverse("api_tareas"), {"titulo": "Intrusión", "proyecto": proyecto.id})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(proyecto.tareas.exists())

    def test_profesor_consulta_y_califica_tareas_de_proyecto(self):
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Entrega")
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(reverse("api_proyectos")).json()["proyectos"][0]["id"], proyecto.id)
        response = self.client.patch(
            reverse("api_calificar_tarea", args=[tarea.id]),
            data=json.dumps({"calificacion": "8.50", "retroalimentacion": "Buen trabajo."}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        tarea.refresh_from_db()
        self.assertEqual(str(tarea.calificacion), "8.50")
        self.assertEqual(tarea.evaluado_por, self.profesor)
        self.assertEqual(tarea.retroalimentacion, "Buen trabajo.")
        self.client.force_login(self.alumno)
        consultada = self.client.get(reverse("api_tarea", args=[tarea.pk])).json()["tarea"]
        self.assertEqual(consultada["calificacion"], "8.50")
        self.assertEqual(consultada["retroalimentacion"], "Buen trabajo.")
        from proyectos.models import DevolucionDocente
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, autor=self.profesor).count(), 1)

    def test_proyecto_solo_visible_y_evaluable_por_docente_asignado(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Entrega")
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(reverse("api_proyecto", args=[proyecto.id])).status_code, 404)
        self.assertEqual(self.client.patch(reverse("api_calificar_tarea", args=[tarea.id]), data=json.dumps({"calificacion": 8}), content_type="application/json").status_code, 404)
        proyecto.profesores.add(self.profesor)
        response = self.json_post(reverse("api_devoluciones", args=[proyecto.id]), {"comentario": "Revisar fuentes", "calificacion": "7.5"})
        self.assertEqual(response.status_code, 201, response.content)
        self.client.force_login(self.alumno)
        self.assertEqual(len(self.client.get(reverse("api_proyecto", args=[proyecto.id])).json()["proyecto"]["devoluciones"]), 1)

    def test_historial_docente_es_aditivo_y_alumno_no_puede_escribirlo(self):
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        self.client.force_login(self.profesor)
        url = reverse("api_devoluciones", args=[proyecto.id])
        self.assertEqual(self.json_post(url, {"comentario": "Primera devolución"}).status_code, 201)
        self.assertEqual(self.json_post(url, {"comentario": "Segunda devolución", "calificacion": 9}).status_code, 201)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.json_post(url, {"calificacion": 10}).status_code, 403)
        self.assertEqual(proyecto.devoluciones.count(), 2)

    def test_devolucion_general_proyecto_se_edita_y_elimina_sin_mezclar_tareas(self):
        from proyectos.models import DevolucionDocente
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Tarea separada")
        self.client.force_login(self.profesor)
        url = reverse("api_devoluciones", args=[proyecto.pk])
        response = self.json_post(url, {"comentario": "Devolución general", "calificacion": "8.25"})
        self.assertEqual(response.status_code, 201)
        original_id = response.json()["devolucion"]["id"]
        replacement = self.client.patch(
            reverse("api_devolucion", args=[original_id]),
            data=json.dumps({"comentario": "Proyecto mejorado"}),
            content_type="application/json",
        )
        self.assertEqual(replacement.status_code, 201)
        current_id = replacement.json()["devolucion"]["id"]
        self.assertEqual(DevolucionDocente.objects.get(pk=current_id).reemplaza_id, original_id)
        self.assertEqual(DevolucionDocente.objects.filter(proyecto=proyecto, anulada_en__isnull=True).count(), 1)
        self.assertFalse(tarea.devoluciones.exists())

        self.client.force_login(self.alumno)
        entries = self.client.get(reverse("api_proyecto", args=[proyecto.pk])).json()["proyecto"]["devoluciones"]
        self.assertEqual([entry["id"] for entry in entries], [current_id])
        self.assertEqual(self.client.delete(reverse("api_devolucion", args=[current_id])).status_code, 404)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.delete(reverse("api_devolucion", args=[current_id])).status_code, 200)

    def test_alumno_no_puede_calificar_y_profesor_no_puede_mutar_tareas(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Entrega")
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.patch(reverse("api_calificar_tarea", args=[tarea.id]), data="{}", content_type="application/json").status_code, 403)
        proyecto.profesores.add(self.profesor)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.patch(reverse("api_tarea", args=[tarea.id]), data=json.dumps({"estado": "completada"}), content_type="application/json").status_code, 403)

    def test_rechaza_fechas_invalidas_e_ignora_prioridad_manual(self):
        self.client.force_login(self.alumno)
        response = self.json_post(reverse("api_tareas"), {"titulo": "Fecha", "fecha_vencimiento": "ayer"})
        self.assertEqual(response.status_code, 400)
        response = self.json_post(reverse("api_tareas"), {"titulo": "Prioridad", "prioridad": "urgente"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["tarea"]["prioridad"], "media")

    def test_entrega_valida_se_lista_solo_al_alumno_y_docente_asignado(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        url = reverse("api_entregas", args=[tarea.pk])
        self.client.force_login(self.companero)
        response = self.client.post(url, {"archivo": SimpleUploadedFile("informe.pdf", b"%PDF-1.7 test", content_type="application/pdf")})
        self.assertEqual(response.status_code, 201, response.content)
        entrega = Entrega.objects.get()
        self.assertEqual(entrega.alumno, self.companero)
        self.assertEqual(self.client.get(url).json()["entregas"][0]["id"], entrega.pk)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.get(url).json()["entregas"][0]["id"], entrega.pk)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(url).status_code, 404)
        proyecto.profesores.add(self.profesor)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(len(self.client.get(url).json()["entregas"]), 1)
        descarga = self.client.get(reverse("descargar_entrega", args=[entrega.pk]))
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(descarga["X-Content-Type-Options"], "nosniff")
        self.assertIn("private", descarga["Cache-Control"])
        descarga.close()

    def test_entrega_rechaza_no_miembro_archivo_invalido_grande_y_duplicado(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        url = reverse("api_entregas", args=[tarea.pk])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.post(url, {"archivo": SimpleUploadedFile("x.pdf", b"%PDF-x")}).status_code, 404)
        self.client.force_login(self.companero)
        self.assertEqual(self.client.post(url, {"archivo": SimpleUploadedFile("x.exe", b"bad")}).status_code, 400)
        self.assertEqual(self.client.post(url, {"archivo": SimpleUploadedFile("x.pdf", b"x" * (10 * 1024 * 1024 + 1))}).status_code, 400)
        data = {"archivo": SimpleUploadedFile("x.pdf", b"%PDF-1.7")}
        self.assertEqual(self.client.post(url, data).status_code, 201)
        self.assertEqual(self.client.post(url, {"archivo": SimpleUploadedFile("y.pdf", b"%PDF-1.7")}).status_code, 409)

    def test_docente_rechaza_y_alumno_reentrega_sin_perder_intentos(self):
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe corregible")
        deliveries_url = reverse("api_entregas", args=[tarea.pk])
        self.client.force_login(self.companero)
        first_response = self.client.post(deliveries_url, {
            "archivo": SimpleUploadedFile("inicial.pdf", b"%PDF-1.7 inicial"),
            "alumno_id": self.ajeno.pk,
        })
        self.assertEqual(first_response.status_code, 201, first_response.content)
        first = Entrega.objects.get(pk=first_response.json()["entrega"]["id"])
        self.assertEqual(first.alumno_id, self.companero.pk)
        first_file_name = first.archivo.name
        self.assertTrue(first.archivo.storage.exists(first_file_name))

        review_url = reverse("api_revision_entrega", args=[tarea.pk, first.pk])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.post(review_url, data=json.dumps({"estado": "rechazada", "devolucion": "Motivo"}), content_type="application/json").status_code, 403)
        self.client.force_login(self.profesor)
        missing_reason = self.client.post(review_url, data=json.dumps({"estado": "rechazada", "devolucion": ""}), content_type="application/json")
        self.assertEqual(missing_reason.status_code, 400)
        rejected = self.client.post(review_url, data=json.dumps({"estado": "rechazada", "devolucion": "Faltan fuentes."}), content_type="application/json")
        self.assertEqual(rejected.status_code, 200, rejected.content)
        first.refresh_from_db()
        self.assertEqual(first.estado, "rechazada")
        self.assertEqual(first.devolucion, "Faltan fuentes.")

        self.client.force_login(self.companero)
        history = self.client.get(deliveries_url).json()["entregas"]
        self.assertEqual(history[0]["devolucion"], "Faltan fuentes.")
        second_response = self.client.post(deliveries_url, {"archivo": SimpleUploadedFile("corregido.pdf", b"%PDF-1.7 corregido")})
        self.assertEqual(second_response.status_code, 201, second_response.content)
        second = Entrega.objects.get(pk=second_response.json()["entrega"]["id"])
        self.assertEqual(second.entrega_anterior_id, first.pk)
        self.assertEqual(second.alumno_id, self.companero.pk)
        self.assertEqual(Entrega.objects.filter(tarea=tarea).count(), 2)
        first.refresh_from_db()
        self.assertEqual(first.estado, "rechazada")
        self.assertEqual(first.devolucion, "Faltan fuentes.")
        self.assertTrue(first.archivo.storage.exists(first_file_name))
        self.assertEqual(len(self.client.get(deliveries_url).json()["entregas"]), 2)
        self.assertEqual(self.client.post(deliveries_url, {"archivo": SimpleUploadedFile("extra.pdf", b"%PDF-1.7 extra")}).status_code, 409)

        self.client.force_login(self.profesor)
        self.assertEqual(self.client.post(review_url, data=json.dumps({"estado": "aprobada"}), content_type="application/json").status_code, 409)
        other_project = Proyecto.objects.create(nombre="Proyecto ajeno", creador=self.ajeno)
        other_task = Tarea.objects.create(creador=self.ajeno, proyecto=other_project, titulo="Otra tarea")
        self.assertEqual(self.client.post(
            reverse("api_revision_entrega", args=[other_task.pk, second.pk]),
            data=json.dumps({"estado": "rechazada", "devolucion": "Ajena"}),
            content_type="application/json",
        ).status_code, 404)

    def test_descarga_privada_autorizada_y_revocada_al_retirar_integrante(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        self.client.force_login(self.companero)
        response = self.client.post(reverse("api_entregas", args=[tarea.pk]), {"archivo": SimpleUploadedFile("x.pdf", b"%PDF-1.7")})
        entrega = Entrega.objects.get(pk=response.json()["entrega"]["id"])
        url = reverse("descargar_entrega", args=[entrega.pk])
        descarga = self.client.get(url)
        self.assertEqual(descarga.status_code, 200)
        descarga.close()
        proyecto.integrantes.remove(self.companero)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_calificacion_rechaza_exceso_de_rango_y_precision(self):
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        self.client.force_login(self.profesor)
        url = reverse("api_calificar_tarea", args=[tarea.pk])
        for nota in ("10.01", "8.555", "NaN", "texto"):
            response = self.client.patch(url, data=json.dumps({"calificacion": nota}), content_type="application/json")
            self.assertEqual(response.status_code, 400, nota)
        self.assertFalse(tarea.devoluciones.exists())

    def test_retirar_integrante_revoca_tareas_y_recalcula_progreso_al_eliminar(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Completada", estado="completada")
        proyecto.actualizar_progreso()
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.progreso, 100)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.patch(
            reverse("api_proyecto", args=[proyecto.pk]),
            data=json.dumps({"integrantes": []}), content_type="application/json",
        ).status_code, 200)
        self.client.force_login(self.companero)
        self.assertEqual(self.client.get(reverse("api_tarea", args=[tarea.pk])).status_code, 404)
        self.assertEqual(self.client.patch(reverse("api_tarea", args=[tarea.pk]), data=json.dumps({"estado": "pendiente"}), content_type="application/json").status_code, 404)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.delete(reverse("api_tarea", args=[tarea.pk])).status_code, 200)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.progreso, 0)

    def test_entrega_grupal_es_compartida_sin_duplicar_por_integrante(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe grupal")
        url = reverse("api_entregas", args=[tarea.pk])
        self.client.force_login(self.companero)
        response = self.client.post(url, {"archivo": SimpleUploadedFile("grupo.pdf", b"%PDF-1.7 entrega")})
        self.assertEqual(response.status_code, 201, response.content)
        entrega = Entrega.objects.get()
        self.assertEqual(entrega.alumno, self.companero)
        self.assertEqual(response.json()["entrega"]["grupo_id"], proyecto.pk)
        self.client.force_login(self.alumno)
        shared = self.client.get(url).json()["entregas"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(shared[0]["id"], entrega.pk)
        shared_download = self.client.get(reverse("descargar_entrega", args=[entrega.pk]))
        self.assertEqual(shared_download.status_code, 200)
        shared_download.close()
        duplicate = self.client.post(url, {"archivo": SimpleUploadedFile("otra.pdf", b"%PDF-1.7 otra")})
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(Entrega.objects.filter(tarea=tarea).count(), 1)

    def test_entregas_grupales_historicas_se_listan_individualmente(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe grupal")
        first = Entrega.objects.create(
            tarea=tarea,
            alumno=self.alumno,
            archivo=SimpleUploadedFile("entrega-a.pdf", b"%PDF-1.7 primera"),
        )
        second = Entrega.objects.create(
            tarea=tarea,
            alumno=self.companero,
            archivo=SimpleUploadedFile("entrega-b.pdf", b"%PDF-1.7 segunda"),
        )
        self.client.force_login(self.alumno)
        response = self.client.get(reverse("api_entregas", args=[tarea.pk]))
        self.assertEqual(response.status_code, 200)
        rows = response.json()["entregas"]
        self.assertEqual({row["id"] for row in rows}, {first.pk, second.pk})
        self.assertEqual({row["alumno_id"] for row in rows}, {self.alumno.pk, self.companero.pk})
        self.assertEqual(len({row["nombre"] for row in rows}), 2)
        self.assertTrue(all(row["nombre"].endswith(".pdf") for row in rows))
        self.assertTrue(all(row["fecha_entrega"] for row in rows))

    def test_entrega_grupal_es_visible_y_descargable_por_docente_autorizado(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe grupal")
        self.client.force_login(self.companero)
        response = self.client.post(
            reverse("api_entregas", args=[tarea.pk]),
            {"archivo": SimpleUploadedFile("grupo.pdf", b"%PDF-1.7 entrega")},
        )
        entrega = Entrega.objects.get(pk=response.json()["entrega"]["id"])
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(reverse("api_entregas", args=[tarea.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("descargar_entrega", args=[entrega.pk])).status_code, 404)
        proyecto.profesores.add(self.profesor)
        listed = self.client.get(reverse("api_entregas", args=[tarea.pk]))
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["entregas"][0]["alumno_id"], self.companero.pk)
        download = self.client.get(reverse("descargar_entrega", args=[entrega.pk]))
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download["Content-Disposition"])
        download.close()
        preview = self.client.get(reverse("descargar_entrega", args=[entrega.pk]) + "?inline=1")
        self.assertEqual(preview.status_code, 200)
        self.assertIn("inline", preview["Content-Disposition"])
        self.assertEqual(preview["Content-Type"], "application/pdf")
        self.assertEqual(preview["Content-Security-Policy"], "sandbox")
        preview.close()

    def test_evaluaciones_grupales_e_individuales_se_aislan_por_alumno(self):
        from proyectos.models import DevolucionDocente

        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        group_url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        first_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.alumno.pk])
        second_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.companero.pk])
        self.client.force_login(self.profesor)
        group = self.client.post(group_url, data=json.dumps({"calificacion": "8.50", "comentario": "Buen trabajo grupal."}), content_type="application/json")
        self.assertEqual(group.status_code, 201, group.content)
        invalid_revision = self.client.post(group_url, data=json.dumps({"calificacion": "10.01"}), content_type="application/json")
        self.assertEqual(invalid_revision.status_code, 400)
        self.assertEqual(self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).json()["grupal"]["calificacion"], "8.50")
        first = self.client.post(first_url, data=json.dumps({"calificacion": "9.00", "comentario": "Aporte destacado."}), content_type="application/json")
        second = self.client.post(second_url, data=json.dumps({"calificacion": "7.50", "comentario": "Aporte suficiente."}), content_type="application/json")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)
        self.assertNotEqual(first.json()["evaluacion"]["calificacion"], second.json()["evaluacion"]["calificacion"])
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="historica").count(), 0)

        self.client.force_login(self.alumno)
        visible = self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).json()
        self.assertEqual(visible["grupal"]["calificacion"], "8.50")
        self.assertEqual([item["alumno_id"] for item in visible["individuales"]], [self.alumno.pk])
        project_view = self.client.get(reverse("api_proyecto", args=[proyecto.pk])).json()["proyecto"]["devoluciones"]
        individual_ids = [entry["alumno_id"] for entry in project_view if entry["tipo"] == "individual"]
        self.assertEqual(individual_ids, [self.alumno.pk])

        self.client.force_login(self.companero)
        visible = self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).json()
        self.assertEqual([item["alumno_id"] for item in visible["individuales"]], [self.companero.pk])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).status_code, 404)

    def test_solo_docente_autorizado_puede_guardar_o_eliminar_evaluaciones(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        group_url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        individual_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.alumno.pk])
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.post(group_url, data="{}", content_type="application/json").status_code, 403)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.post(group_url, data="{}", content_type="application/json").status_code, 403)
        self.assertEqual(self.client.delete(individual_url).status_code, 403)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.post(individual_url, data=json.dumps({"calificacion": 8}), content_type="application/json").status_code, 404)

    def test_eliminar_y_recrear_evaluaciones_preserva_historial_y_entrega(self):
        from proyectos.models import DevolucionDocente

        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        self.client.force_login(self.companero)
        posted = self.client.post(
            reverse("api_entregas", args=[tarea.pk]),
            {"archivo": SimpleUploadedFile("grupo.pdf", b"%PDF-1.7 entrega")},
        )
        entrega = Entrega.objects.get(pk=posted.json()["entrega"]["id"])
        storage = entrega.archivo.storage
        storage_name = entrega.archivo.name

        self.client.force_login(self.profesor)
        group_url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        first_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.alumno.pk])
        second_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.companero.pk])
        self.client.post(group_url, data=json.dumps({"calificacion": 8}), content_type="application/json")
        self.client.post(first_url, data=json.dumps({"calificacion": 9}), content_type="application/json")
        self.client.post(second_url, data=json.dumps({"calificacion": 7}), content_type="application/json")
        self.assertEqual(self.client.delete(group_url).status_code, 200)
        self.assertEqual(self.client.delete(first_url).status_code, 200)
        current = self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).json()
        self.assertIsNone(current["grupal"])
        self.assertEqual([item["alumno_id"] for item in current["individuales"]], [self.companero.pk])
        self.assertTrue(Entrega.objects.filter(pk=entrega.pk).exists())
        self.assertTrue(storage.exists(storage_name))
        history = self.client.get(reverse("api_proyecto", args=[proyecto.pk])).json()["proyecto"]["devoluciones"]
        annulled = [entry for entry in history if entry["anulada"]]
        self.assertEqual(len(annulled), 2)
        self.assertTrue(all(entry["anulada_en"] and entry["anulada_por"] for entry in annulled))

        self.assertEqual(self.client.post(group_url, data=json.dumps({"calificacion": 8.5}), content_type="application/json").status_code, 201)
        self.assertEqual(self.client.post(first_url, data=json.dumps({"calificacion": 9.5}), content_type="application/json").status_code, 201)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="grupal").count(), 2)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="individual", alumno=self.alumno).count(), 2)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, anulada_en__isnull=False).count(), 2)

    def test_repetir_evaluacion_no_crea_version_duplicada_y_corregir_conserva_historial(self):
        from proyectos.models import DevolucionDocente

        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        payload = json.dumps({"calificacion": "8.25", "comentario": "Buen trabajo."})
        self.client.force_login(self.profesor)

        created = self.client.post(url, data=payload, content_type="application/json")
        repeated = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.json()["sin_cambios"])
        self.assertEqual(created.json()["evaluacion"]["id"], repeated.json()["evaluacion"]["id"])
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="grupal").count(), 1)

        corrected = self.client.post(
            url,
            data=json.dumps({"calificacion": "9.00", "comentario": "Trabajo corregido."}),
            content_type="application/json",
        )
        self.assertEqual(corrected.status_code, 201)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="grupal").count(), 2)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, tipo="grupal", anulada_en__isnull=True).count(), 2)
        previous = DevolucionDocente.objects.get(pk=created.json()["evaluacion"]["id"])
        self.assertIsNone(previous.anulada_en)

        individual_url = reverse("api_evaluacion_individual", args=[tarea.pk, self.alumno.pk])
        individual_payload = json.dumps({"calificacion": "7.50", "comentario": "Aporte individual."})
        first_individual = self.client.post(individual_url, data=individual_payload, content_type="application/json")
        repeated_individual = self.client.post(individual_url, data=individual_payload, content_type="application/json")
        self.assertEqual(first_individual.status_code, 201)
        self.assertEqual(repeated_individual.status_code, 200)
        self.assertEqual(first_individual.json()["evaluacion"]["id"], repeated_individual.json()["evaluacion"]["id"])
        self.assertEqual(
            DevolucionDocente.objects.filter(tarea=tarea, tipo="individual", alumno=self.alumno, anulada_en__isnull=True).count(),
            1,
        )

    def test_devoluciones_independientes_edicion_versionada_y_eliminacion_protegida(self):
        from proyectos.models import DevolucionDocente

        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Ensayo")
        url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        self.client.force_login(self.profesor)
        comment_only = self.client.post(url, data=json.dumps({"comentario": "Revisar la conclusión."}), content_type="application/json")
        grade_only = self.client.post(url, data=json.dumps({"calificacion": "8.75"}), content_type="application/json")
        self.assertEqual(comment_only.status_code, 201)
        self.assertEqual(grade_only.status_code, 201)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, anulada_en__isnull=True).count(), 2)
        history = self.client.get(reverse("api_evaluaciones", args=[tarea.pk])).json()["historial"]
        self.assertEqual(len(history), 2)

        feedback_id = comment_only.json()["evaluacion"]["id"]
        edit_url = reverse("api_devolucion", args=[feedback_id])
        edited = self.client.patch(
            edit_url,
            data=json.dumps({"comentario": "Conclusión corregida.", "calificacion": "9.00"}),
            content_type="application/json",
        )
        self.assertEqual(edited.status_code, 201, edited.content)
        replacement_id = edited.json()["devolucion"]["id"]
        replacement = DevolucionDocente.objects.get(pk=replacement_id)
        self.assertEqual(replacement.reemplaza_id, feedback_id)
        self.assertEqual(DevolucionDocente.objects.get(pk=feedback_id).anulada_por, self.profesor)
        self.assertEqual(DevolucionDocente.objects.filter(tarea=tarea, anulada_en__isnull=True).count(), 2)

        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.delete(reverse("api_devolucion", args=[replacement_id])).status_code, 404)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.delete(reverse("api_devolucion", args=[replacement_id])).status_code, 200)
        self.assertIsNotNone(DevolucionDocente.objects.get(pk=replacement_id).anulada_en)


    def test_evaluaciones_rechazan_notas_invalidas_y_post_sin_csrf(self):
        proyecto = self.crear_proyecto()
        proyecto.profesores.add(self.profesor)
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Informe")
        url = reverse("api_evaluacion_grupal", args=[tarea.pk])
        self.client.force_login(self.profesor)
        for grade in ("10.01", "8.555", "NaN", "texto"):
            response = self.client.post(url, data=json.dumps({"calificacion": grade}), content_type="application/json")
            self.assertEqual(response.status_code, 400, grade)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.profesor)
        response = csrf_client.post(url, data=json.dumps({"calificacion": 8}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_asignacion_individual_entrega_correccion_edicion_anulacion_y_permisos(self):
        url = reverse("api_asignaciones")
        self.client.force_login(self.profesor)
        assigned = self.json_post(url, {"alumno_id": self.alumno.pk, "titulo": "Ensayo", "descripcion": "Argumentar", "fecha_vencimiento": "2026-11-20"})
        self.assertEqual(assigned.status_code, 201, assigned.content)
        tarea = Tarea.objects.get(pk=assigned.json()["asignacion"]["tarea_id"])
        self.assertEqual(AsignacionTarea.objects.get(tarea=tarea).profesor, self.profesor)

        student_client = Client()
        student_client.force_login(self.alumno)
        self.assertEqual([row["id"] for row in student_client.get(reverse("api_tareas")).json()["tareas"]], [tarea.pk])
        self.assertEqual(student_client.patch(reverse("api_tarea", args=[tarea.pk]), data=json.dumps({"titulo": "Alterada"}), content_type="application/json").status_code, 403)
        self.assertEqual(student_client.delete(reverse("api_tarea", args=[tarea.pk])).status_code, 403)
        delivery_response = student_client.post(reverse("api_entregas", args=[tarea.pk]), {"archivo": SimpleUploadedFile("trabajo.pdf", b"%PDF-1.7 entrega"), "observaciones": "Entrega final"})
        self.assertEqual(delivery_response.status_code, 201, delivery_response.content)
        delivery_id = delivery_response.json()["entrega"]["id"]
        delivery = Entrega.objects.get(pk=delivery_id)

        queue = self.client.get(url)
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()["asignaciones"][0]["entregas"][0]["alumno_id"], self.alumno.pk)
        correction_url = reverse("api_correccion_entrega", args=[delivery_id])
        comment = self.json_post(correction_url, {"comentario": "Buen desarrollo, completa la conclusión."})
        self.assertEqual(comment.status_code, 201, comment.content)
        self.assertEqual(comment.json()["correccion"]["calificacion"], "")
        self.assertEqual(comment.json()["correccion"]["comentario"], "Buen desarrollo, completa la conclusión.")
        visible = student_client.get(correction_url).json()["correccion"]
        self.assertEqual(visible["calificacion"], "")
        self.assertEqual(visible["comentario"], "Buen desarrollo, completa la conclusión.")
        self.assertEqual(visible["estado"], "corregida")
        self.assertEqual(visible["fecha"], comment.json()["correccion"]["fecha"])
        grade_only_edit = self.client.put(correction_url, data=json.dumps({"calificacion": "7.25"}), content_type="application/json")
        self.assertEqual(grade_only_edit.status_code, 201, grade_only_edit.content)
        grade = self.json_post(correction_url, {"calificacion": "8.50"})
        self.assertEqual(grade.status_code, 201, grade.content)
        delivery.refresh_from_db()
        self.assertEqual(delivery.estado, "aprobada")
        visible = student_client.get(correction_url).json()["correccion"]
        self.assertEqual(visible["calificacion"], "8.50")
        self.assertEqual(visible["comentario"], "")

        edited = self.client.put(correction_url, data=json.dumps({"comentario": "Revisar la conclusión", "estado": "devuelta"}), content_type="application/json")
        self.assertEqual(edited.status_code, 201, edited.content)
        visible = student_client.get(correction_url).json()["correccion"]
        self.assertEqual(visible["calificacion"], "")
        self.assertEqual(visible["comentario"], "Revisar la conclusión")
        self.assertEqual(Entrega.objects.get(pk=delivery_id).estado, "rechazada")

        self.assertEqual(self.client.delete(correction_url).status_code, 200)
        self.assertIsNone(student_client.get(correction_url).json()["correccion"])
        self.assertEqual(Entrega.objects.get(pk=delivery_id).estado, "entregada")
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse("api_tarea", args=[tarea.pk])).status_code, 404)
        self.assertEqual(self.client.get(correction_url).status_code, 404)


class EntregaConcurrenteTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        self._settings = override_settings(PRIVATE_MEDIA_ROOT=self._media.name)
        self._settings.enable()
        self.addCleanup(self._settings.disable)
        storage = Entrega._meta.get_field("archivo").storage
        previous_location = storage.location
        storage.location = self._media.name
        self.addCleanup(setattr, storage, "location", previous_location)
        self.alumno = Usuario.objects.create_user(
            dni="40200001", password="ClaveSegura_2026!", email="concurrente-a@example.test",
        )
        PerfilUsuario.objects.create(usuario=self.alumno, rol="alumno")
        self.companero = Usuario.objects.create_user(
            dni="40200002", password="ClaveSegura_2026!", email="concurrente-b@example.test",
        )
        PerfilUsuario.objects.create(usuario=self.companero, rol="alumno")
        self.proyecto = Proyecto.objects.create(nombre="Concurrente", creador=self.alumno)
        self.proyecto.integrantes.add(self.alumno, self.companero)
        self.tarea = Tarea.objects.create(creador=self.alumno, proyecto=self.proyecto, titulo="Entrega")

    @skipUnlessDBFeature("has_select_for_update")
    def test_dos_entregas_simultaneas_crean_una_sola_entrega_grupal(self):
        url = reverse("api_entregas", args=[self.tarea.pk])
        barrier = Barrier(2)

        def submit(user, filename):
            close_old_connections()
            try:
                client = Client()
                client.force_login(user)
                barrier.wait(timeout=10)
                response = client.post(
                    url,
                    {"archivo": SimpleUploadedFile(filename, b"%PDF-1.7 concurrente")},
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda values: submit(*values),
                ((self.alumno, "a.pdf"), (self.companero, "b.pdf")),
            ))

        self.assertCountEqual(results, [201, 409])
        self.assertEqual(Entrega.objects.filter(tarea=self.tarea).count(), 1)
