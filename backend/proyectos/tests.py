import json
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from archivos.models import Archivo
from .models import Proyecto
from usuarios.models import PerfilUsuario


Usuario = get_user_model()


class CreacionProyectoAlumnoTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.storage = Archivo._meta.get_field("archivo").storage
        self.previous_storage_location = self.storage.location
        self.storage.location = self.media.name
        self.addCleanup(setattr, self.storage, "location", self.previous_storage_location)
        self.alumno = Usuario.objects.create_user(dni="60100001", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.alumno, rol="alumno")
        self.ajeno = Usuario.objects.create_user(dni="60100003", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.ajeno, rol="alumno")
        self.profesor = Usuario.objects.create_user(dni="60100002", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.profesor, rol="profesor")
        self.client = Client()
        self.assertTrue(self.client.login(dni="60100001", password="ClaveSegura_2026!"))

    def crear_proyecto(self, nombre, descripcion="", fecha_entrega=""):
        return self.client.post(
            reverse("api_proyectos"),
            data=json.dumps({
                "nombre": nombre,
                "descripcion": descripcion,
                "fecha_entrega": fecha_entrega,
                "integrantes": [],
                "creador_id": self.ajeno.pk,
            }),
            content_type="application/json",
        )

    def test_alumno_crea_lista_visualiza_y_elimina_proyectos_calificados_o_no(self):
        page = self.client.get(reverse("core:alumno"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="newProjectBtn"')

        existing = Proyecto.objects.create(nombre="Proyecto preexistente", creador=self.alumno)
        existing.integrantes.add(self.alumno)
        existing.profesores.add(self.profesor)

        unreviewed_response = self.crear_proyecto(
            "Proyecto sin revisar", "Creado desde la sesión del alumno", "2026-12-01",
        )
        self.assertEqual(unreviewed_response.status_code, 201, unreviewed_response.content)
        unreviewed_id = unreviewed_response.json()["proyecto"]["id"]
        self.assertEqual(unreviewed_response.json()["proyecto"]["creador_id"], self.alumno.pk)

        graded_response = self.crear_proyecto("Proyecto con archivo", "Con adjunto")
        self.assertEqual(graded_response.status_code, 201, graded_response.content)
        graded_id = graded_response.json()["proyecto"]["id"]
        graded = Proyecto.objects.get(pk=graded_id)
        self.assertEqual(graded.creador_id, self.alumno.pk)

        uploaded = self.client.post(reverse("api_archivos"), {
            "archivo": SimpleUploadedFile("material.pdf", b"%PDF-1.4 material del proyecto", "application/pdf"),
        })
        self.assertEqual(uploaded.status_code, 201, uploaded.content)
        file_id = uploaded.json()["archivo"]["id"]
        attached = self.client.post(
            reverse("api_archivos_proyecto", args=[graded_id]),
            data=json.dumps({"archivo_id": file_id}),
            content_type="application/json",
        )
        self.assertEqual(attached.status_code, 200, attached.content)

        student_listing = self.client.get(reverse("api_proyectos")).json()["proyectos"]
        self.assertEqual({row["id"] for row in student_listing}, {existing.pk, unreviewed_id, graded_id})
        self.assertEqual(
            self.client.get(reverse("api_proyecto", args=[unreviewed_id])).json()["proyecto"]["nombre"],
            "Proyecto sin revisar",
        )
        detail = self.client.get(reverse("api_proyecto", args=[graded_id])).json()["proyecto"]
        self.assertEqual([item["id"] for item in detail["archivos_adjuntos"]], [file_id])

        graded.profesores.add(self.profesor)
        teacher_client = Client()
        teacher_client.force_login(self.profesor)
        teacher_list = teacher_client.get(reverse("api_proyectos")).json()["proyectos"]
        self.assertIn(graded_id, {row["id"] for row in teacher_list})
        self.assertEqual(
            teacher_client.get(reverse("api_proyecto", args=[graded_id])).json()["proyecto"]["id"],
            graded_id,
        )
        feedback = teacher_client.post(
            reverse("api_devoluciones", args=[graded_id]),
            data=json.dumps({"calificacion": "8.50", "comentario": "Buen trabajo."}),
            content_type="application/json",
        )
        self.assertEqual(feedback.status_code, 201, feedback.content)

        self.assertEqual(self.client.delete(reverse("api_proyecto", args=[unreviewed_id])).status_code, 200)
        self.assertFalse(Proyecto.objects.filter(pk=unreviewed_id).exists())
        self.assertTrue(Proyecto.objects.filter(pk=graded_id).exists())
        self.assertTrue(Proyecto.objects.filter(pk=existing.pk).exists())

        self.assertEqual(self.client.delete(reverse("api_proyecto", args=[graded_id])).status_code, 200)
        self.assertFalse(Proyecto.objects.filter(pk=graded_id).exists())
        self.assertTrue(Archivo.objects.filter(pk=file_id).exists())
        self.assertTrue(Proyecto.objects.filter(pk=existing.pk).exists())
        self.assertEqual({row["id"] for row in self.client.get(reverse("api_proyectos")).json()["proyectos"]}, {existing.pk})
        self.assertEqual({row["id"] for row in teacher_client.get(reverse("api_proyectos")).json()["proyectos"]}, {existing.pk})

# Create your tests here.
