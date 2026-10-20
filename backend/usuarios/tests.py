from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import PerfilUsuario

Usuario = get_user_model()


class AutenticacionTests(TestCase):
    def registro_data(self, **overrides):
        data = {
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@example.com",
            "dni": "40123456",
            "password": "UnaClaveSegura_2026!",
        }
        data.update(overrides)
        return data

    def crear_usuario(self, dni="40123456", password="ClaveSegura_2026!", rol="alumno"):
        usuario = Usuario.objects.create_user(
            dni=dni,
            password=password,
            first_name="Ana",
            last_name="Pérez",
            email=f"{dni}@example.com",
        )
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        return usuario

    def test_registro_valido_crea_alumno_con_password_hash(self):
        response = self.client.post(reverse("usuarios:registro"), self.registro_data())
        usuario = Usuario.objects.get(dni="40123456")
        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertEqual(usuario.perfil.rol, "alumno")
        self.assertTrue(usuario.check_password("UnaClaveSegura_2026!"))
        self.assertNotEqual(usuario.password, "UnaClaveSegura_2026!")

    def test_dni_duplicado_muestra_error_y_no_crea_otra_cuenta(self):
        self.crear_usuario()
        response = self.client.post(
            reverse("usuarios:registro"),
            self.registro_data(email="otra@example.com"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una cuenta registrada con ese DNI")
        self.assertEqual(Usuario.objects.filter(dni="40123456").count(), 1)

    def test_inicio_sesion_correcto_por_dni(self):
        self.crear_usuario()
        response = self.client.post(
            reverse("usuarios:login"),
            {"dni": "40123456", "password": "ClaveSegura_2026!", "remember": "on"},
        )
        self.assertRedirects(
            response,
            reverse("core:inicio"),
            fetch_redirect_response=False,
        )
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_inicio_sesion_incorrecto(self):
        self.crear_usuario()
        response = self.client.post(
            reverse("usuarios:login"),
            {"dni": "40123456", "password": "incorrecta"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "El DNI o la contraseña son incorrectos")

    def test_cierre_de_sesion_requiere_post_y_cierra_sesion(self):
        usuario = self.crear_usuario()
        self.client.force_login(usuario)
        self.assertEqual(self.client.get(reverse("usuarios:logout")).status_code, 405)
        response = self.client.post(reverse("usuarios:logout"))
        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_pagina_protegida_redirige_a_usuario_anonimo(self):
        response = self.client.get(reverse("core:alumno"))
        self.assertRedirects(response, f"{reverse('usuarios:login')}?next={reverse('core:alumno')}")

    def test_rutas_academicas_exigen_autenticacion(self):
        for name in ("lista_tareas", "lista_proyectos", "lista_archivos", "lista_documentos"):
            with self.subTest(route=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("usuarios:login")))

    def test_post_sin_csrf_es_rechazado(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("usuarios:login"),
            {"dni": "40123456", "password": "ClaveSegura_2026!"},
        )
        self.assertEqual(response.status_code, 403)

    def test_alumno_no_accede_a_pagina_docente(self):
        self.client.force_login(self.crear_usuario())
        self.assertEqual(self.client.get(reverse("core:profesor")).status_code, 403)

    def test_alumno_accede_a_su_panel(self):
        self.client.force_login(self.crear_usuario())
        response = self.client.get(reverse("core:alumno"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cerrar sesión")

    def test_profesor_no_accede_a_pagina_de_alumno(self):
        self.client.force_login(self.crear_usuario(dni="40987654", rol="profesor"))
        self.assertEqual(self.client.get(reverse("core:alumno")).status_code, 403)

    def test_profesor_accede_a_su_panel(self):
        self.client.force_login(self.crear_usuario(dni="40987654", rol="profesor"))
        response = self.client.get(reverse("core:profesor"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cerrar sesión")

    def test_formulario_no_permite_elevar_rol_a_profesor(self):
        response = self.client.post(
            reverse("usuarios:registro"),
            self.registro_data(role="profesor", is_staff="on", is_superuser="on"),
        )
        usuario = Usuario.objects.get(dni="40123456")
        self.assertRedirects(response, reverse("usuarios:login"))
        self.assertEqual(usuario.perfil.rol, "alumno")
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
