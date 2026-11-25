/* ==========================================================================
   AvenirStack · Configuración editable
   --------------------------------------------------------------------------
   Todo lo que cambia con datos reales vive acá. No hace falta tocar el
   HTML ni el resto del JavaScript.

   - Dejá un valor vacío ("") para que el sitio muestre un marcador
     "Por configurar" en lugar de inventar datos.
   - No guardes contraseñas, claves privadas ni tokens en este archivo:
     es público para quien visite el sitio.
   ========================================================================== */
window.AVENIRSTACK_CONFIG = {

  /* Texto pequeño del pie de página. Dejalo vacío ("") para ocultarlo. */
  footerNote: "AvenirStack es una empresa ficticia creada con fines demostrativos.",

  /* ---------- EduFlow ---------- */
  eduflow: {
    // Dirección de la plataforma real. Ej.: "https://eduflow.tudominio.com"
    // Vacío = el botón «Conocer EduFlow» avisa que todavía no hay enlace.
    url: "/"
  },

  /* ---------- Contacto ---------- */
  contact: {
    // Correo público de contacto. Ej.: "contacto@tudominio.com"
    email: "avenirstack@gmail.com",

    // Dirección que recibe el formulario (servicio de formularios o backend propio).
    // Vacío = el formulario valida, pero NO envía ni simula un envío.
    formEndpoint: "",

    // Método HTTP con el que se envía el formulario.
    formMethod: "POST"
  },

  /* ---------- Redes sociales ----------
     Agregá, quitá o reordená entradas. Las que tengan url vacía se muestran
     como "Por configurar". */
  social: [
    { label: "LinkedIn",  url: "" },
    { label: "GitHub",    url: "" },
    { label: "Instagram", url: "" }
  ],

  /* ---------- Equipo ----------
     name:        nombre que se muestra
     area:        área de trabajo
     role:        cargo (opcional, vacío = no se muestra)
     description: descripción breve (opcional)
     photo:       ruta de la foto, ej. "assets/lucca.jpg" (vacío = espacio reservado)
     skills:      tecnologías y conocimientos */
  team: [
    {
      name: "Lucca Julian Sosa Alvarenga",
      area: "Desarrollo Full Stack",
      role: "",
      description: "",
      photo: "/static/avenirstack/assets/Lucca.jpg",
      skills: ["Python", "Django", "MySQL", "HTML", "CSS", "JavaScript"]
    },
    {
      name: "Carla Juliana Fernandez",
      area: "Desarrollo Full Stack",
      role: "",
      description: "",
      photo: "/static/avenirstack/assets/Carla.jpeg",
      skills: ["Django", "MySQL", "HTML", "CSS", "JavaScript"]
    },
    {
      name: "Aaron Giezi Josias Suarez Luna",
      area: "Desarrollo de software",
      role: "",
      description: "",
      photo: "/static/avenirstack/assets/Aaron.jpeg",
      skills: ["Django", "HTML", "CSS", "JavaScript"]
    }
  ]
};
