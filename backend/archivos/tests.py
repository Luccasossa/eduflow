import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from django.test import Client, TestCase
from django.urls import reverse

from proyectos.models import Proyecto
from usuarios.models import PerfilUsuario
from .models import Archivo, Carpeta

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

    def test_hash_sha256_busqueda_parcial_y_borrado_seguro(self):
        self.client.force_login(self.alumno)
        first = self.upload("Apunte.pdf", b"%PDF-1.4\ncontenido A")
        self.assertEqual(first.status_code, 201)
        duplicate = self.upload("renombrado.pdf", b"%PDF-1.4\ncontenido A")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["error"], "Este archivo ya se encuentra en tus archivos.")
        second = self.upload("Apunte-final.pdf", b"%PDF-1.4\ncontenido B")
        self.assertEqual(second.status_code, 201)
        folder = self.client.post(reverse("api_carpetas"), {"nombre": "Sistemas"}).json()["carpeta"]
        move = self.client.post(reverse("mover_archivo", args=[first.json()["archivo"]["id"]]), {"carpeta": folder["id"]})
        self.assertEqual(move.status_code, 200)
        folder_map = self.client.get(reverse("api_archivos")).json()["carpeta_por_archivo"]
        self.assertEqual(folder_map[str(first.json()["archivo"]["id"])]["nombre"], "Sistemas")
        matches = self.client.get(reverse("api_archivos"), {"buscar": "APUNTE-f"}).json()["archivos"]
        self.assertEqual([item["nombre"] for item in matches], ["Apunte-final.pdf"])

        archivo = Archivo.objects.get(nombre_original="Apunte-final.pdf")
        storage_name = archivo.archivo.name
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.delete(reverse("eliminar_archivo", args=[archivo.pk])).status_code, 404)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.delete(reverse("eliminar_archivo", args=[archivo.pk])).status_code, 200)
        self.assertFalse(Archivo.objects.filter(pk=archivo.pk).exists())
        self.assertFalse(self.file_field.storage.exists(storage_name))

    def test_rechaza_extension_y_contenido_invalidos(self):
        self.client.force_login(self.alumno)
        response = self.upload("virus.exe", b"MZ binary")
        self.assertEqual(response.status_code, 400)
        response = self.upload("falso.pdf", b"texto plano")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Archivo.objects.count(), 0)

    def test_permite_archivos_sql_y_zip_con_contenido_coherente(self):
        self.client.force_login(self.alumno)
        sql = self.upload("base_datos.sql", b"CREATE TABLE libros (id INTEGER);\n")
        archive = self.upload("codigo.zip", b"PK\x03\x04contenido")
        self.assertEqual(sql.status_code, 201, sql.content)
        self.assertEqual(archive.status_code, 201, archive.content)

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

    def test_carpetas_solo_visibles_para_su_propietario_y_nombre_validado(self):
        self.client.force_login(self.alumno)
        response = self.client.post(reverse("api_carpetas"), {"nombre": "  Material  "})
        self.assertEqual(response.status_code, 201)
        carpeta = Carpeta.objects.get()
        self.assertEqual(carpeta.nombre, "Material")
        self.assertEqual(response.json()["carpeta"], {"id": carpeta.id, "nombre": "Material"})
        self.assertEqual(self.client.get(reverse("api_carpetas")).json()["carpetas"], [{"id": carpeta.id, "nombre": "Material"}])

        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(reverse("api_carpetas")).json()["carpetas"], [])
        self.assertEqual(self.client.post(reverse("api_archivos"), {
            "archivo": SimpleUploadedFile("guia.pdf", b"%PDF-1.4\ncontenido", "application/pdf"),
            "carpeta": carpeta.id,
        }).status_code, 404)
        for nombre in ("", " " * 2, "../privado", "x" * 151):
            self.assertEqual(self.client.post(reverse("api_carpetas"), {"nombre": nombre}).status_code, 400)

    def test_listado_filtra_por_proyecto_y_carpeta_y_no_expone_archivos_ajenos(self):
        proyecto = Proyecto.objects.create(nombre="Equipo", creador=self.alumno)
        proyecto.integrantes.add(self.alumno, self.ajeno)
        carpeta = Carpeta.objects.create(nombre="Equipo", propietario=self.alumno)
        self.client.force_login(self.alumno)
        response = self.upload(proyecto=proyecto.id, carpeta=carpeta.id)
        self.assertEqual(response.status_code, 201, response.content)
        compartido = Archivo.objects.get()
        self.client.force_login(self.ajeno)
        listed = self.client.get(reverse("api_archivos"), {"proyecto": proyecto.id}).json()["archivos"]
        self.assertEqual([item["id"] for item in listed], [compartido.id])
        self.assertEqual(set(listed[0]), {"id", "nombre", "tamano", "fecha_subida", "proyecto_id", "descarga"})
        self.assertEqual(listed[0]["nombre"], "guia.pdf")
        self.assertEqual(listed[0]["proyecto_id"], proyecto.id)
        self.assertEqual(self.client.get(reverse("api_archivos"), {"carpeta": carpeta.id}).status_code, 404)

    def test_subida_tarea_valida_vinculo_y_restringe_tarea_ajena(self):
        from tareas.models import Tarea

        proyecto = Proyecto.objects.create(nombre="Equipo", creador=self.alumno)
        proyecto.integrantes.add(self.alumno, self.ajeno)
        tarea = Tarea.objects.create(titulo="Entrega", creador=self.alumno, proyecto=proyecto)
        otro_proyecto = Proyecto.objects.create(nombre="Otro", creador=self.alumno)
        self.client.force_login(self.alumno)
        response = self.upload(tarea=tarea.id)
        self.assertEqual(response.status_code, 201, response.content)
        archivo = Archivo.objects.get()
        self.assertEqual(archivo.tarea, tarea)
        self.assertEqual(archivo.proyecto, proyecto)
        self.assertTrue(tarea.archivos_adjuntos.filter(pk=archivo.pk).exists())
        self.assertEqual(self.upload("otro.pdf", b"%PDF-1.4\ncontenido", proyecto=otro_proyecto.id, tarea=tarea.id).status_code, 400)

        self.client.force_login(self.ajeno)
        self.assertEqual(self.upload("intruso.pdf", b"%PDF-1.4\ncontenido", tarea=tarea.id).status_code, 201)

    def test_adjuntos_de_tareas_del_proyecto_son_independientes_y_se_pueden_quitar(self):
        from tareas.models import Tarea

        proyecto = Proyecto.objects.create(nombre="Biblioteca", creador=self.alumno)
        proyecto.integrantes.add(self.alumno)
        analisis = Tarea.objects.create(titulo="Análisis", creador=self.alumno, proyecto=proyecto)
        diseno = Tarea.objects.create(titulo="Diseño", creador=self.alumno, proyecto=proyecto)
        self.client.force_login(self.alumno)

        first = self.upload("requisitos.pdf", b"%PDF-1.4\nrequisitos", tarea=analisis.pk)
        second = self.upload("modelo.pdf", b"%PDF-1.4\nmodelo", tarea=diseno.pk)
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)

        first_id = first.json()["archivo"]["id"]
        second_id = second.json()["archivo"]["id"]
        analisis_json = self.client.get(reverse("api_tarea", args=[analisis.pk])).json()["tarea"]
        diseno_json = self.client.get(reverse("api_tarea", args=[diseno.pk])).json()["tarea"]
        self.assertEqual([item["id"] for item in analisis_json["archivos_adjuntos"]], [first_id])
        self.assertEqual([item["id"] for item in diseno_json["archivos_adjuntos"]], [second_id])
        self.assertEqual(analisis_json["archivos_adjuntos"][0]["extension"], "PDF")
        self.assertGreater(analisis_json["archivos_adjuntos"][0]["tamano"], 0)
        self.assertTrue(analisis_json["archivos_adjuntos"][0]["fecha_subida"])

        storage_name = Archivo.objects.get(pk=first_id).archivo.name
        detached = self.client.delete(
            reverse("api_archivos_tarea", args=[analisis.pk]),
            data='{"archivo_id": %d}' % first_id,
            content_type="application/json",
        )
        self.assertEqual(detached.status_code, 200, detached.content)
        self.assertFalse(analisis.archivos_adjuntos.filter(pk=first_id).exists())
        self.assertTrue(Archivo.objects.filter(pk=first_id, propietario=self.alumno).exists())
        self.assertTrue(self.file_field.storage.exists(storage_name))
        self.assertEqual(self.client.get(reverse("api_tarea", args=[diseno.pk])).json()["tarea"]["archivos_adjuntos"][0]["id"], second_id)

        linked_file = Archivo.objects.get(pk=second_id)
        linked_storage_name = linked_file.archivo.name
        deleted = self.client.delete(reverse("eliminar_archivo", args=[second_id]))
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(Tarea.objects.filter(pk=diseno.pk).exists())
        self.assertFalse(diseno.archivos_adjuntos.filter(pk=second_id).exists())
        self.assertFalse(Archivo.objects.filter(pk=second_id).exists())
        self.assertFalse(self.file_field.storage.exists(linked_storage_name))

    def test_rechaza_carga_sin_archivo_y_ids_malformados(self):
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.post(reverse("api_archivos")).status_code, 400)
        response = self.client.post(reverse("api_archivos"), {
            "archivo": SimpleUploadedFile("guia.pdf", b"%PDF-1.4\ncontenido", "application/pdf"),
            "proyecto": "no-es-un-id",
        })
        self.assertEqual(response.status_code, 400)

    def test_descarga_requiere_autenticacion_y_rechaza_archivo_ajeno(self):
        self.client.force_login(self.alumno)
        self.upload()
        archivo = Archivo.objects.get()
        self.client.logout()
        self.assertEqual(self.client.get(reverse("descargar_archivo", args=[archivo.id])).status_code, 302)

    def test_post_de_archivos_y_carpetas_exige_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alumno)
        self.assertEqual(client.post(reverse("api_carpetas"), {"nombre": "Material"}).status_code, 403)
        self.assertEqual(client.post(reverse("api_archivos"), {
            "archivo": SimpleUploadedFile("guia.pdf", b"%PDF-1.4\ncontenido", "application/pdf"),
        }).status_code, 403)
