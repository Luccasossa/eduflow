import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Proyecto
from usuarios.models import PerfilUsuario
from .models import Archivo

Usuario = get_user_model()


class ArchivosTests(TestCase):
    def setUp(self):
        self.file_field = Archivo._meta.get_field("archivo")
        self.original_storage = self.file_field.storage
        self.test_storage_dir = tempfile.TemporaryDirectory(prefix="eduflow-private-test-")
        self.file_field.storage = FileSystemStorage(location=self.test_storage_dir.name, base_url=None)
        self.alumno = Usuario.objects.create_user(dni="50100001", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.alumno, rol="alumno")
        self.ajeno = Usuario.objects.create_user(dni="50100002", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.ajeno, rol="alumno")
        self.profesor = Usuario.objects.create_user(dni="50100003", password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=self.profesor, rol="profesor")

    def tearDown(self):
        for archivo in Archivo.objects.all():
            archivo.archivo.delete(save=False)
        self.file_field.storage = self.original_storage
        self.test_storage_dir.cleanup()

    def upload(self, name="guia.pdf", content=b"%PDF-1.4\ncontenido", **fields):
        return self.client.post(reverse("api_archivos"), {"archivo": SimpleUploadedFile(name, content, "application/pdf"), **fields})

    def test_subida_listado_y_descarga_privada(self):
        self.client.force_login(self.alumno)
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        archivo = Archivo.objects.get()
        self.assertEqual(archivo.propietario, self.alumno)
        self.assertNotIn("guia.pdf", archivo.archivo.name)
        self.assertEqual(self.client.get(reverse("api_archivos")).json()["archivos"][0]["nombre"], "guia.pdf")
        descarga = self.client.get(reverse("descargar_archivo", args=[archivo.id]))
        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(b"".join(descarga.streaming_content), b"%PDF-1.4\ncontenido")
        self.assertEqual(descarga["X-Content-Type-Options"], "nosniff")
        descarga.close()

    def test_rechaza_extension_y_contenido_invalidos(self):
        self.client.force_login(self.alumno)
        response = self.upload("virus.exe", b"MZ binary")
        self.assertEqual(response.status_code, 400)
        response = self.upload("falso.pdf", b"texto plano")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Archivo.objects.count(), 0)

    def test_rechaza_archivo_demasiado_grande(self):
        self.client.force_login(self.alumno)
        with patch("archivos.views.MAX_UPLOAD_SIZE", 8):
            response = self.upload(content=b"%PDF-1.4\ncontenido")
        self.assertEqual(response.status_code, 400)

    def test_descarga_no_autorizada_y_proyecto_compartido(self):
        self.client.force_login(self.alumno)
        self.upload()
        archivo = Archivo.objects.get()
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse("descargar_archivo", args=[archivo.id])).status_code, 404)

        proyecto = Proyecto.objects.create(nombre="Equipo", creador=self.alumno)
        proyecto.integrantes.add(self.alumno, self.ajeno)
        archivo.proyecto = proyecto
        archivo.save()
        descarga_autorizada = self.client.get(reverse("descargar_archivo", args=[archivo.id]))
        self.assertEqual(descarga_autorizada.status_code, 200)
        descarga_autorizada.close()

    def test_profesor_lista_archivos_y_usuario_sin_login_es_redirigido(self):
        self.client.force_login(self.alumno)
        self.upload()
        privado = Archivo.objects.get()
        self.client.force_login(self.profesor)
        self.assertEqual(len(self.client.get(reverse("api_archivos")).json()["archivos"]), 0)
        proyecto = Proyecto.objects.create(nombre="Curso", creador=self.alumno)
        proyecto.integrantes.add(self.alumno)
        proyecto.profesores.add(self.profesor)
        privado.proyecto = proyecto
        privado.save()
        self.assertEqual(len(self.client.get(reverse("api_archivos")).json()["archivos"]), 1)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("api_archivos")).status_code, 302)

    def test_profesor_comparte_archivo_en_proyecto_y_alumno_integrante_lo_descarga(self):
        proyecto = Proyecto.objects.create(nombre="Cátedra", creador=self.alumno)
        proyecto.integrantes.add(self.alumno)
        proyecto.profesores.add(self.profesor)
        self.client.force_login(self.profesor)
        response = self.upload(proyecto=proyecto.id)
        self.assertEqual(response.status_code, 201)
        archivo = Archivo.objects.get()
        self.assertEqual(archivo.propietario, self.profesor)
        self.client.force_login(self.alumno)
        self.assertEqual(len(self.client.get(reverse("api_archivos") + f"?proyecto={proyecto.id}").json()["archivos"]), 1)
        descarga = self.client.get(reverse("descargar_archivo", args=[archivo.id]))
        self.assertEqual(descarga.status_code, 200)
        descarga.close()
