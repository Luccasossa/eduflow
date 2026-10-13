// ========================================
// NAVEGACIÓN
// ========================================

const navItems = document.querySelectorAll(".nav-item[data-section]");
const sections = document.querySelectorAll(".section");
const pageTitle = document.getElementById("page-title");

navItems.forEach(item => {

    item.addEventListener("click", function(event) {

        event.preventDefault();

        const sectionId = this.dataset.section;

        // Quitar activo
        navItems.forEach(nav => {
            nav.classList.remove("active");
        });

        // Activar botón
        this.classList.add("active");

        // Ocultar secciones
        sections.forEach(section => {
            section.classList.remove("active-section");
        });

        // Mostrar sección
        const selectedSection = document.getElementById(sectionId);

        if (selectedSection) {
            selectedSection.classList.add("active-section");
        }

        // Cambiar título
        pageTitle.textContent = this.textContent.trim();

    });

});


// ========================================
// MODO OSCURO
// ========================================

const themeBtn = document.getElementById("themeBtn");

themeBtn.addEventListener("click", () => {

    document.body.classList.toggle("dark");

    if (document.body.classList.contains("dark")) {

        themeBtn.textContent = "☀️";

    } else {

        themeBtn.textContent = "🌙";

    }

});


// ========================================
// MODAL NUEVA TAREA
// ========================================

const taskModal = document.getElementById("taskModal");
const newTaskBtn = document.getElementById("newTaskBtn");
const closeModal = document.getElementById("closeModal");
const saveTask = document.getElementById("saveTask");

newTaskBtn.addEventListener("click", () => {

    taskModal.classList.add("show");

});


closeModal.addEventListener("click", () => {

    taskModal.classList.remove("show");

});


taskModal.addEventListener("click", event => {

    if (event.target === taskModal) {

        taskModal.classList.remove("show");

    }

});


// ========================================
// CREAR TAREA
// ========================================

saveTask.addEventListener("click", () => {

    const taskInput = document.getElementById("taskInput");
    const priorityInput = document.getElementById("priorityInput");

    const taskName = taskInput.value.trim();

    if (taskName === "") {

        alert("Por favor ingresá el nombre de la tarea.");

        return;

    }

    alert(
        `Tarea creada correctamente.\n\n` +
        `Nombre: ${taskName}\n` +
        `Prioridad: ${priorityInput.value}`
    );

    taskInput.value = "";

    taskModal.classList.remove("show");

});


// ========================================
// COMPLETAR TAREAS
// ========================================

const taskChecks = document.querySelectorAll(".task-check");

taskChecks.forEach(check => {

    check.addEventListener("click", () => {

        check.style.background = "#2563eb";
        check.style.borderColor = "#2563eb";

        check.innerHTML = "✓";
        check.style.color = "white";
        check.style.fontSize = "12px";
        check.style.display = "flex";
        check.style.alignItems = "center";
        check.style.justifyContent = "center";

    });

});


// ========================================
// NOTIFICACIONES
// ========================================

const notificationBtn =
    document.getElementById("notificationBtn");

notificationBtn.addEventListener("click", () => {

    alert(
        "🔔 Notificaciones\n\n" +
        "• Nueva tarea agregada\n" +
        "• María editó un documento\n" +
        "• Tenés una entrega próxima"
    );

});

// ========================================
// ACCESOS RÁPIDOS
// ========================================

const quickCards = document.querySelectorAll(".quick-card");

quickCards.forEach(card => {

    card.addEventListener("click", () => {

        const sectionId = card.dataset.section;

        const navButton = document.querySelector(
            `.nav-item[data-section="${sectionId}"]`
        );

        if (navButton) {
            navButton.click();
        }

    });

});

// ========================================
// MODO OSCURO
// ========================================

const darkModeSwitch =
    document.getElementById("darkModeSwitch");


darkModeSwitch.addEventListener("change", function() {

    if (this.checked) {

        document.body.classList.add("dark");

        localStorage.setItem(
            "darkMode",
            "true"
        );

    } else {

        document.body.classList.remove("dark");

        localStorage.setItem(
            "darkMode",
            "false"
        );

    }

});

// ========================================
// RECUPERAR MODO OSCURO
// ========================================

const savedDarkMode =
    localStorage.getItem("darkMode");


if (savedDarkMode === "true") {

    document.body.classList.add("dark");

    darkModeSwitch.checked = true;

}

// ========================================
// CONFIGURACIÓN
// ========================================

const settingsBtn =
    document.getElementById("settingsBtn");

const teacherViewBtn =
    document.getElementById("teacherViewBtn");

teacherViewBtn.addEventListener("click", () => {
    document.body.classList.add("teacher-mode");
});


settingsBtn.addEventListener("click", () => {

    alert(
        "⚙️ Configuración\n\n" +
        "Desde acá podrás personalizar:\n\n" +
        "• Perfil\n" +
        "• Notificaciones\n" +
        "• Apariencia\n" +
        "• Privacidad\n" +
        "• Preferencias"
    );

});

