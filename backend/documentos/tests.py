import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from proyectos.models import Proyecto
from usuarios.models import PerfilUsuario
from .models import Documento

Usuario = get_user_model()


class DocumentosTests(TestCase):
    def usuario(self, dni, rol="alumno"):
        user = Usuario.objects.create_user(dni=dni, password="ClaveSegura_2026!")
        PerfilUsuario.objects.create(usuario=user, rol=rol)
        return user

    def setUp(self):
        self.alumno = self.usuario("60100001")
        self.comp = self.usuario("60100002")
        self.ajeno = self.usuario("60100003")
        self.profesor = self.usuario("60100004", "profesor")

    def post_json(self, url, data):
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def test_creacion_edicion_persistencia_y_conflicto_de_version(self):
        self.client.force_login(self.alumno)
        response = self.post_json(reverse("api_documentos"), {"titulo": "Apuntes", "contenido": "Versión inicial"})
        self.assertEqual(response.status_code, 201)
        documento = Documento.objects.get()
        self.assertEqual(documento.creador, self.alumno)
        url = reverse("api_documento", args=[documento.id])
        response = self.client.patch(url, data=json.dumps({"titulo": "Apuntes", "contenido": "Guardado", "version": 1}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        documento.refresh_from_db()
        self.assertEqual(documento.contenido, "Guardado")
        self.assertEqual(documento.version, 2)
        self.assertEqual(self.client.get(url).json()["documento"]["contenido"], "Guardado")
        response = self.client.patch(url, data=json.dumps({"contenido": "Sobrescribir", "version": 1}), content_type="application/json")
        self.assertEqual(response.status_code, 409)
        documento.refresh_from_db()
        self.assertEqual(documento.contenido, "Guardado")

    def test_colaboradores_de_proyecto_pueden_editar_y_ajenos_no(self):
        proyecto = Proyecto.objects.create(nombre="Proyecto de grupo", creador=self.alumno)
        proyecto.integrantes.add(self.alumno, self.comp)
        self.client.force_login(self.alumno)
        response = self.post_json(reverse("api_documentos"), {"titulo": "Informe", "contenido": "A", "proyecto": proyecto.id})
        self.assertEqual(response.status_code, 201)
        documento = Documento.objects.get()
        self.assertTrue(documento.colaboradores.filter(pk=self.comp.pk).exists())
        self.client.force_login(self.comp)
        url = reverse("api_documento", args=[documento.id])
        response = self.client.patch(url, data=json.dumps({"contenido": "B", "version": 1}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.patch(url, data=json.dumps({"contenido": "X", "version": 2}), content_type="application/json").status_code, 404)

    def test_profesor_solo_lectura_y_alumno_no_puede_elevar_permisos(self):
        proyecto = Proyecto.objects.create(nombre="Curso", creador=self.alumno)
        proyecto.integrantes.add(self.alumno)
        proyecto.profesores.add(self.profesor)
        self.client.force_login(self.alumno)
        self.post_json(reverse("api_documentos"), {"titulo": "Informe", "contenido": "Texto", "proyecto": proyecto.id})
        documento = Documento.objects.get()
        url = reverse("api_documento", args=[documento.id])
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.patch(url, data=json.dumps({"contenido": "Cambio", "version": 1}), content_type="application/json").status_code, 403)
        self.client.force_login(self.ajeno)
        self.assertEqual(self.post_json(reverse("api_documentos"), {"titulo": "X", "creador": self.alumno.id}).status_code, 201)
        creado = Documento.objects.order_by("-id").first()
        self.assertEqual(creado.creador, self.ajeno)

    def test_eliminar_solo_por_creador(self):
        documento = Documento.objects.create(titulo="Privado", creador=self.alumno)
        self.client.force_login(self.ajeno)
        self.assertEqual(self.client.delete(reverse("api_documento", args=[documento.id])).status_code, 404)
        self.client.force_login(self.alumno)
        self.assertEqual(self.client.delete(reverse("api_documento", args=[documento.id])).status_code, 200)

    def test_retirar_integrante_revoca_acceso_a_documento_del_proyecto(self):
        proyecto = Proyecto.objects.create(nombre="Equipo", creador=self.alumno)
        proyecto.profesores.add(self.profesor)
        proyecto.integrantes.add(self.alumno, self.comp)
        documento = Documento.objects.create(titulo="Compartido", contenido="Texto", creador=self.alumno, proyecto=proyecto)
        documento.colaboradores.add(self.comp)
        proyecto.integrantes.remove(self.comp)
        self.client.force_login(self.comp)
        self.assertEqual(self.client.get(reverse("api_documento", args=[documento.id])).status_code, 404)

    def test_profesor_persiste_retroalimentacion_solo_en_documentos_grupales(self):
        proyecto = Proyecto.objects.create(nombre="Equipo", creador=self.alumno)
        proyecto.profesores.add(self.profesor)
        documento = Documento.objects.create(titulo="Informe", creador=self.alumno, proyecto=proyecto)
        self.client.force_login(self.profesor)
        response = self.client.patch(
            reverse("api_evaluar_documento", args=[documento.id]),
            data=json.dumps({"calificacion": "8.50", "retroalimentacion": "Buen análisis"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        documento.refresh_from_db()
        self.assertEqual(str(documento.calificacion), "8.50")
        self.assertEqual(documento.retroalimentacion, "Buen análisis")
        self.assertEqual(proyecto.devoluciones.filter(documento=documento, autor=self.profesor).count(), 1)
        privado = Documento.objects.create(titulo="Personal", creador=self.alumno)
        self.assertEqual(self.client.patch(
            reverse("api_evaluar_documento", args=[privado.id]),
            data=json.dumps({"retroalimentacion": "No"}), content_type="application/json",
        ).status_code, 404)

    def test_docente_no_asignado_no_puede_ver_ni_evaluar_documento_de_proyecto(self):
        proyecto = Proyecto.objects.create(nombre="Proyecto restringido", creador=self.alumno)
        documento = Documento.objects.create(titulo="Informe", creador=self.alumno, proyecto=proyecto)
        self.client.force_login(self.profesor)
        self.assertEqual(self.client.get(reverse("api_documento", args=[documento.id])).status_code, 404)
        self.assertEqual(self.client.patch(
            reverse("api_evaluar_documento", args=[documento.id]),
            data=json.dumps({"retroalimentacion": "Sin autorización"}), content_type="application/json",
        ).status_code, 404)

    def test_calificacion_documento_respeta_rango_precision_y_registra_historial_solo_al_validar(self):
        proyecto = Proyecto.objects.create(nombre="Proyecto", creador=self.alumno)
        proyecto.profesores.add(self.profesor)
        documento = Documento.objects.create(titulo="Informe", creador=self.alumno, proyecto=proyecto)
        self.client.force_login(self.profesor)
        url = reverse("api_evaluar_documento", args=[documento.pk])
        for calificacion in ("10.01", "8.555", "NaN", "texto"):
            response = self.client.patch(
                url, data=json.dumps({"calificacion": calificacion}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400, calificacion)
        self.assertFalse(documento.devoluciones.exists())
        response = self.client.patch(
            url, data=json.dumps({"calificacion": "9.25", "retroalimentacion": "Bien"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.alumno)
        self.assertEqual(
            self.client.get(reverse("api_documento", args=[documento.pk])).json()["documento"]["calificacion"],
            "9.25",
        )

    def test_profesor_crea_y_edita_su_documento_de_catedra_privado(self):
        self.client.force_login(self.profesor)
        response = self.post_json(reverse("api_documentos"), {"titulo": "Guía", "contenido": "Borrador"})
        self.assertEqual(response.status_code, 201)
        documento = Documento.objects.get()
        self.assertEqual(documento.creador, self.profesor)
        self.client.force_login(self.alumno)
        self.assertNotIn(documento.id, [item["id"] for item in self.client.get(reverse("api_documentos")).json()["documentos"]])
        self.client.force_login(self.profesor)
        response = self.client.patch(
            reverse("api_documento", args=[documento.id]),
            data=json.dumps({"titulo": "Guía", "contenido": "Publicable", "version": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        documento.refresh_from_db()
        self.assertEqual(documento.contenido, "Publicable")
