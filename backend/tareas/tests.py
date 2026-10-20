import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Proyecto
from usuarios.models import PerfilUsuario
from .models import Tarea

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
        self.assertEqual(tarea.prioridad, "baja")
        self.assertEqual(tarea.fecha_vencimiento.isoformat(), "2026-11-05")
        response = self.client.get(reverse("api_tareas") + "?estado=en_progreso&prioridad=baja&desde=2026-11-01&hasta=2026-11-30")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.json()["tareas"]], [tarea.id])

    def test_elimina_tarea_propia(self):
        tarea = Tarea.objects.create(creador=self.alumno, titulo="Eliminar")
        self.client.force_login(self.alumno)
        response = self.client.delete(reverse("api_tarea", args=[tarea.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Tarea.objects.filter(pk=tarea.pk).exists())

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

    def test_creador_puede_eliminar_su_proyecto_y_tareas_de_equipo(self):
        proyecto = self.crear_proyecto()
        Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Tarea asociada")
        self.client.force_login(self.alumno)
        response = self.client.delete(reverse("api_proyecto", args=[proyecto.id]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Proyecto.objects.filter(pk=proyecto.pk).exists())
        self.assertFalse(Tarea.objects.filter(proyecto_id=proyecto.pk).exists())

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

    def test_alumno_no_puede_calificar_y_profesor_no_puede_mutar_tareas(self):
        proyecto = self.crear_proyecto()
        tarea = Tarea.objects.create(creador=self.alumno, proyecto=proyecto, titulo="Entrega")
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.patch(reverse("api_calificar_tarea", args=[tarea.id]), data="{}", content_type="application/json").status_code, 403)
        proyecto.profesores.add(self.profesor)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.patch(reverse("api_tarea", args=[tarea.id]), data=json.dumps({"estado": "completada"}), content_type="application/json").status_code, 403)

    def test_rechaza_fechas_y_prioridades_invalidas(self):
        self.client.force_login(self.alumno)
        response = self.json_post(reverse("api_tareas"), {"titulo": "Fecha", "fecha_vencimiento": "ayer"})
        self.assertEqual(response.status_code, 400)
        response = self.json_post(reverse("api_tareas"), {"titulo": "Prioridad", "prioridad": "urgente"})
        self.assertEqual(response.status_code, 400)
