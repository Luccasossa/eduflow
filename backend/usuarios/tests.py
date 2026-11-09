from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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


class PerfilYSeguridadTests(TestCase):
    def setUp(self):
        self.user = Usuario.objects.create_user(
            dni="40123456", password="ClaveSegura_2026!", first_name="Ana", last_name="PÃ©rez",
            email="40123456@example.com",
        )
        PerfilUsuario.objects.create(usuario=self.user, rol="alumno")
        self.client.force_login(self.user)

    def test_api_perfil_devuelve_datos_autenticados(self):
        response = self.client.get(reverse("usuarios:api_perfil"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["perfil"], {
            "nombres": "Ana", "apellidos": "PÃ©rez", "correo": "40123456@example.com",
            "dni": "40123456", "rol": "alumno", "especialidad": "",
        })

    def test_api_perfil_muestra_rol_docente_de_la_cuenta_autenticada(self):
        teacher = Usuario.objects.create_user(dni="40987654", password="ClaveSegura_2026!", first_name="Luis", email="profesor@example.com")
        PerfilUsuario.objects.create(usuario=teacher, rol="profesor", especialidad="GAO")
        self.client.force_login(teacher)
        response = self.client.get(reverse("usuarios:api_perfil"))
        self.assertEqual(response.json()["perfil"]["rol"], "profesor")
        self.assertEqual(response.json()["perfil"]["especialidad"], "GAO")

    def test_api_perfil_y_contrasena_requieren_sesion_y_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("usuarios:api_perfil")).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(reverse("usuarios:api_cambiar_contrasena"), {
            "contrasena_actual": "ClaveSegura_2026!", "nueva_contrasena": "NuevaClave_Fuerte_2027!",
            "confirmacion": "NuevaClave_Fuerte_2027!",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_especialidad_se_registra_una_vez_y_no_se_puede_reemplazar(self):
        url = reverse("usuarios:api_perfil")
        first = self.client.patch(url, data='{"especialidad":"IPP"}', content_type="application/json")
        changed = self.client.patch(url, data='{"especialidad":"GAO"}', content_type="application/json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(changed.status_code, 409)
        self.user.perfil.refresh_from_db()
        self.assertEqual(self.user.perfil.especialidad, "IPP")

    def test_especialidad_rechaza_valores_invalidos_y_modelo_bloquea_cambio(self):
        response = self.client.patch(reverse("usuarios:api_perfil"), data='{"especialidad":"OTRA"}', content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.user.perfil.especialidad = "TP"
        self.user.perfil.save()
        self.user.perfil.especialidad = "IPP"
        with self.assertRaises(ValidationError):
            self.user.perfil.save()

    def test_cambio_contrasena_validado_actualiza_hash_y_conserva_sesion(self):
        response = self.client.post(reverse("usuarios:api_cambiar_contrasena"), {
            "contrasena_actual": "ClaveSegura_2026!", "nueva_contrasena": "NuevaClave_Fuerte_2027!",
            "confirmacion": "NuevaClave_Fuerte_2027!",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NuevaClave_Fuerte_2027!"))

    def test_cambio_contrasena_rechaza_actual_incorrecta_y_confirmacion_distinta(self):
        url = reverse("usuarios:api_cambiar_contrasena")
        payload = {"contrasena_actual": "incorrecta", "nueva_contrasena": "NuevaClave_Fuerte_2027!", "confirmacion": "NuevaClave_Fuerte_2027!"}
        self.assertEqual(self.client.post(url, payload, content_type="application/json").status_code, 400)
        payload["contrasena_actual"] = "ClaveSegura_2026!"
        payload["confirmacion"] = "OtraClave_Fuerte_2027!"
        self.assertEqual(self.client.post(url, payload, content_type="application/json").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveSegura_2026!"))

    def test_cambio_contrasena_aplica_validadores_de_django(self):
        response = self.client.post(reverse("usuarios:api_cambiar_contrasena"), {
            "contrasena_actual": "ClaveSegura_2026!", "nueva_contrasena": "123", "confirmacion": "123",
        }, content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
