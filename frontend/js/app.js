(() => {
    const $ = (selector) => document.querySelector(selector);
    const $$ = (selector) => [...document.querySelectorAll(selector)];
    const csrf = $('[name="csrfmiddlewaretoken"]')?.value || "";
    const taskUrl = "/tareas/api/";
    const projectUrl = "/proyectos/api/";
    const states = [
        ["pendiente", "Por hacer"],
        ["en_progreso", "En proceso"],
        ["completada", "Finalizado"],
    ];
    let personalTasks = [];
    let projects = [];
    let students = [];
    let editingTask = null;
    let taskProjectId = null;
    let editingProject = null;

    async function api(url, method = "GET", data = undefined) {
        const options = { method, headers: { Accept: "application/json" } };
        if (data !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.headers["X-CSRFToken"] = csrf;
            options.body = JSON.stringify(data);
        }
        const response = await fetch(url, options);
        let payload = {};
        try { payload = await response.json(); } catch (_) { /* respuesta vacía */ }
        if (response.redirected) {
            window.location.assign(response.url);
            throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
        }
        if (!response.ok) throw new Error(payload.error || "No se pudo completar la operación.");
        return payload;
    }

    function notify(message, error = false) {
        let toast = $("#academicToast");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "academicToast";
            toast.className = "academic-toast";
            toast.setAttribute("role", "status");
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.toggle("error", error);
        toast.classList.add("visible");
        window.clearTimeout(toast._timer);
        toast._timer = window.setTimeout(() => toast.classList.remove("visible"), 3000);
    }

    function make(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function dateLabel(value) {
        return value ? new Date(`${value}T12:00:00`).toLocaleDateString("es-AR") : "Sin fecha de entrega";
    }

    // Navegación del dashboard existente.
    const navItems = $$('.nav-item[data-section]');
    navItems.forEach((item) => item.addEventListener("click", (event) => {
        event.preventDefault();
        navItems.forEach((nav) => nav.classList.toggle("active", nav === item));
        $$(".section").forEach((section) => section.classList.toggle("active-section", section.id === item.dataset.section));
        const title = $("#page-title");
        if (title) title.textContent = item.textContent.trim();
    }));
    $$(".quick-card[data-section]").forEach((card) => card.addEventListener("click", () => {
        document.querySelector(`.nav-item[data-section="${card.dataset.section}"]`)?.click();
    }));
    $("#viewAllTasksBtn")?.addEventListener("click", () => document.querySelector('.nav-item[data-section="tareas"]')?.click());

    const themeBtn = $("#themeBtn");
    themeBtn?.addEventListener("click", () => document.body.classList.toggle("dark"));
    const darkModeSwitch = $("#darkModeSwitch");
    if (darkModeSwitch) {
        darkModeSwitch.checked = localStorage.getItem("darkMode") === "true";
        document.body.classList.toggle("dark", darkModeSwitch.checked);
        darkModeSwitch.addEventListener("change", () => {
            document.body.classList.toggle("dark", darkModeSwitch.checked);
            localStorage.setItem("darkMode", String(darkModeSwitch.checked));
        });
    }
    $("#settingsBtn")?.addEventListener("click", () => notify("La configuración de perfil estará disponible próximamente."));

    const taskModal = $("#taskModal");
    const projectModal = $("#projectModal");
    function closeTaskModal() { taskModal?.classList.remove("show"); }
    function closeProjectModal() { projectModal?.classList.remove("show"); }

    function renderTasks() {
        const board = $("#personalKanban");
        if (!board) return;
        board.replaceChildren();
        states.forEach(([state, label]) => {
            const tasks = personalTasks.filter((task) => task.estado === state);
            const column = make("div", "kanban-column");
            const heading = make("div", "kanban-title", label);
            heading.appendChild(make("b", "", String(tasks.length)));
            column.appendChild(heading);
            if (!tasks.length) column.appendChild(make("p", "empty-state", "No hay tareas en este estado."));
            tasks.forEach((task) => {
                const card = make("article", `kanban-card${state === "completada" ? " completed" : ""}`);
                card.appendChild(make("strong", "", task.titulo));
                if (task.descripcion) card.appendChild(make("p", "", task.descripcion));
                card.appendChild(make("span", "card-date", `${dateLabel(task.fecha_vencimiento)} · Prioridad ${task.prioridad}`));
                const actions = make("div", "task-card-actions");
                const stateSelect = document.createElement("select");
                stateSelect.setAttribute("aria-label", `Estado de ${task.titulo}`);
                states.forEach(([value, text]) => {
                    const option = new Option(text, value, false, task.estado === value);
                    stateSelect.add(option);
                });
                stateSelect.addEventListener("change", async () => {
                    try { await api(`${taskUrl}${task.id}/`, "PATCH", { estado: stateSelect.value }); await loadTasks(); }
                    catch (error) { notify(error.message, true); }
                });
                const edit = make("button", "text-button", "Editar");
                edit.type = "button";
                edit.addEventListener("click", () => openTask(task));
                const remove = make("button", "text-button danger-text", "Eliminar");
                remove.type = "button";
                remove.addEventListener("click", () => deleteTask(task));
                actions.append(stateSelect, edit, remove);
                card.appendChild(actions);
                column.appendChild(card);
            });
            board.appendChild(column);
        });
        const count = personalTasks.length;
        const pending = personalTasks.filter((task) => task.estado !== "completada").length;
        $("#taskCountText")?.replaceChildren(document.createTextNode(`${pending} tareas pendientes`));
        $("#taskSummaryText")?.replaceChildren(document.createTextNode(`Tienes ${pending} tareas por finalizar.`));
        renderUpcomingTasks();
    }

    function renderUpcomingTasks() {
        const list = $("#upcomingTaskList");
        if (!list) return;
        list.replaceChildren();
        const upcoming = [...personalTasks]
            .filter((task) => task.estado !== "completada")
            .sort((a, b) => (a.fecha_vencimiento || "9999").localeCompare(b.fecha_vencimiento || "9999"))
            .slice(0, 3);
        if (!upcoming.length) {
            list.appendChild(make("p", "empty-state", "No tienes tareas pendientes."));
            return;
        }
        upcoming.forEach((task) => {
            const row = make("div", "task");
            row.appendChild(make("div", "task-check", task.estado === "completada" ? "✓" : ""));
            const info = make("div", "task-info");
            info.appendChild(make("strong", "", task.titulo));
            info.appendChild(make("span", "", dateLabel(task.fecha_vencimiento)));
            row.appendChild(info);
            row.appendChild(make("span", `priority ${task.prioridad}`, task.prioridad));
            list.appendChild(row);
        });
    }

    function taskFilters() {
        const params = new URLSearchParams();
        const status = $("#filterTaskStatus")?.value;
        const priority = $("#filterTaskPriority")?.value;
        const from = $("#filterTaskFrom")?.value;
        const to = $("#filterTaskTo")?.value;
        if (status) params.set("estado", status);
        if (priority) params.set("prioridad", priority);
        if (from) params.set("desde", from);
        if (to) params.set("hasta", to);
        return params.toString();
    }

    async function loadTasks() {
        try {
            const query = taskFilters();
            personalTasks = (await api(`${taskUrl}${query ? `?${query}` : ""}`)).tareas;
            renderTasks();
        } catch (error) { notify(error.message, true); }
    }

    function openTask(task = null, projectId = null) {
        editingTask = task;
        taskProjectId = projectId || task?.proyecto_id || null;
        $("#taskModalTitle").textContent = task ? "Editar tarea" : (taskProjectId ? "Nueva tarea del equipo" : "Nueva tarea");
        $("#taskInput").value = task?.titulo || "";
        $("#taskDescription").value = task?.descripcion || "";
        $("#taskDueDate").value = task?.fecha_vencimiento || "";
        $("#priorityInput").value = task?.prioridad || "media";
        $("#taskStateInput").value = task?.estado || "pendiente";
        $("#taskFormError").textContent = "";
        $("#deleteTaskBtn").hidden = !task;
        taskModal.classList.add("show");
        $("#taskInput").focus();
    }

    async function saveTask() {
        const data = {
            titulo: $("#taskInput").value.trim(),
            descripcion: $("#taskDescription").value.trim(),
            fecha_vencimiento: $("#taskDueDate").value,
            prioridad: $("#priorityInput").value,
            estado: $("#taskStateInput").value,
        };
        if (!data.titulo) { $("#taskFormError").textContent = "Escribe un título para la tarea."; return; }
        if (!editingTask && taskProjectId) data.proyecto = taskProjectId;
        try {
            if (editingTask) await api(`${taskUrl}${editingTask.id}/`, "PATCH", data);
            else await api(taskUrl, "POST", data);
            closeTaskModal();
            await Promise.all([loadTasks(), loadProjects()]);
            notify(editingTask ? "Tarea actualizada." : "Tarea creada.");
        } catch (error) { $("#taskFormError").textContent = error.message; }
    }

    async function deleteTask(task) {
        if (!window.confirm(`¿Eliminar la tarea “${task.titulo}”?`)) return;
        try {
            await api(`${taskUrl}${task.id}/`, "DELETE", {});
            await Promise.all([loadTasks(), loadProjects()]);
            notify("Tarea eliminada.");
        } catch (error) { notify(error.message, true); }
    }

    function renderProjects() {
        const list = $("#studentProjectList");
        if (!list) return;
        list.replaceChildren();
        if (!projects.length) list.appendChild(make("p", "empty-state", "Todavía no perteneces a proyectos grupales."));
        projects.forEach((project) => {
            const card = make("article", "project-card");
            card.appendChild(make("div", "project-icon", "▣"));
            card.appendChild(make("h3", "", project.nombre));
            card.appendChild(make("p", "", project.descripcion || "Sin descripción."));
            card.appendChild(make("p", "project-due-date", `Entrega: ${dateLabel(project.fecha_entrega)}`));
            const progress = make("div", "progress");
            const track = make("div", "progress-bar");
            const fill = make("div");
            fill.style.width = `${project.progreso}%`;
            track.appendChild(fill);
            progress.append(track, make("span", "", `${project.progreso}%`));
            card.appendChild(progress);
            card.appendChild(make("div", "project-members", `Integrantes: ${project.integrantes.map((member) => member.nombre).join(", ")}`));

            const actions = make("div", "project-actions");
            const addTask = make("button", "secondary-button", "+ Tarea del equipo");
            addTask.type = "button";
            addTask.addEventListener("click", () => openTask(null, project.id));
            actions.appendChild(addTask);
            if (project.puede_editar) {
                const edit = make("button", "text-button", "Editar proyecto");
                edit.type = "button";
                edit.addEventListener("click", () => openProject(project));
                actions.appendChild(edit);
            }
            card.appendChild(actions);

            const taskList = make("div", "project-task-list");
            taskList.appendChild(make("h4", "", "Tareas del equipo"));
            if (!project.tareas.length) taskList.appendChild(make("p", "empty-state", "Todavía no hay tareas."));
            project.tareas.forEach((task) => {
                const row = make("div", "project-task-row");
                const details = make("div");
                details.appendChild(make("strong", "", task.titulo));
                details.appendChild(make("small", "", `${states.find(([value]) => value === task.estado)?.[1] || task.estado} · ${task.prioridad} · ${dateLabel(task.fecha_vencimiento)}`));
                row.appendChild(details);
                const editTask = make("button", "text-button", "Editar");
                editTask.type = "button";
                editTask.addEventListener("click", () => openTask(task));
                row.appendChild(editTask);
                taskList.appendChild(row);
            });
            card.appendChild(taskList);
            list.appendChild(card);
        });
        $("#projectCountText")?.replaceChildren(document.createTextNode(`${projects.length} proyectos grupales`));
    }

    async function loadProjects() {
        try {
            projects = (await api(projectUrl)).proyectos;
            renderProjects();
        } catch (error) { notify(error.message, true); }
    }

    async function openProject(project = null) {
        editingProject = project;
        $("#projectModalTitle").textContent = project ? "Editar proyecto" : "Nuevo proyecto grupal";
        $("#projectNameInput").value = project?.nombre || "";
        $("#projectDescriptionInput").value = project?.descripcion || "";
        $("#projectDueDateInput").value = project?.fecha_entrega || "";
        $("#projectFormError").textContent = "";
        $("#deleteProjectBtn").hidden = !project;
        try {
            students = (await api("/proyectos/api/alumnos/")).alumnos;
            const select = $("#projectMembersInput");
            select.replaceChildren();
            students.filter((member) => !project || member.id !== project.creador_id).forEach((member) => {
                const option = new Option(member.nombre, member.id);
                option.selected = Boolean(project?.integrantes.some((current) => current.id === member.id));
                select.add(option);
            });
            projectModal.classList.add("show");
            $("#projectNameInput").focus();
        } catch (error) { notify(error.message, true); }
    }

    async function saveProject() {
        const data = {
            nombre: $("#projectNameInput").value.trim(),
            descripcion: $("#projectDescriptionInput").value.trim(),
            fecha_entrega: $("#projectDueDateInput").value,
            integrantes: [...$("#projectMembersInput").selectedOptions].map((option) => Number(option.value)),
        };
        if (!data.nombre) { $("#projectFormError").textContent = "Escribe un nombre para el proyecto."; return; }
        try {
            if (editingProject) await api(`${projectUrl}${editingProject.id}/`, "PATCH", data);
            else await api(projectUrl, "POST", data);
            closeProjectModal();
            await loadProjects();
            notify(editingProject ? "Proyecto actualizado." : "Proyecto creado.");
        } catch (error) { $("#projectFormError").textContent = error.message; }
    }

    async function deleteProject() {
        if (!editingProject || !window.confirm(`¿Eliminar “${editingProject.nombre}” y sus tareas de equipo?`)) return;
        try {
            await api(`${projectUrl}${editingProject.id}/`, "DELETE", {});
            closeProjectModal();
            await loadProjects();
            notify("Proyecto eliminado.");
        } catch (error) { $("#projectFormError").textContent = error.message; }
    }

    $$('[data-new-task]').forEach((button) => button.addEventListener("click", () => openTask()));
    $("#newProjectBtn")?.addEventListener("click", () => openProject());
    $("#saveTask")?.addEventListener("click", saveTask);
    $("#closeModal")?.addEventListener("click", closeTaskModal);
    $("#deleteTaskBtn")?.addEventListener("click", () => editingTask && deleteTask(editingTask).then(closeTaskModal));
    $("#saveProjectBtn")?.addEventListener("click", saveProject);
    $("#deleteProjectBtn")?.addEventListener("click", deleteProject);
    $$('[data-close-project]').forEach((button) => button.addEventListener("click", closeProjectModal));
    taskModal?.addEventListener("click", (event) => { if (event.target === taskModal) closeTaskModal(); });
    projectModal?.addEventListener("click", (event) => { if (event.target === projectModal) closeProjectModal(); });
    ["#filterTaskStatus", "#filterTaskPriority", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => {
        $(selector)?.addEventListener("change", loadTasks);
    });
    $("#clearTaskFilters")?.addEventListener("click", () => {
        ["#filterTaskStatus", "#filterTaskPriority", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => { if ($(selector)) $(selector).value = ""; });
        loadTasks();
    });
    $("#notificationBtn")?.addEventListener("click", () => notify("No tienes notificaciones nuevas."));

    loadTasks();
    loadProjects();
})();
