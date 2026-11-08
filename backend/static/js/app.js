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
    let academicFiles = [];
    let folders = [];
    let fileFolders = {};
    let fileManagement = {};
    let academicDocuments = [];
    let editingDocument = null;
    let documentConflictPending = false;
    let documentConflictVersion = null;
    let latestConflictDocument = null;
    let documentSession = 0;
    let documentListRequest = 0;
    let documentSaveInFlight = false;

    async function api(url, method = "GET", data = undefined) {
        const options = { method, headers: { Accept: "application/json" } };
        if (data !== undefined) {
            options.headers["Content-Type"] = "application/json";
            options.headers["X-CSRFToken"] = csrf;
            options.body = JSON.stringify(data);
        }
        let response;
        try {
            response = await fetch(url, options);
        } catch (_) {
            throw new Error("No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.");
        }
        let payload = {};
        try { payload = await response.json(); } catch (_) { /* respuesta vacía */ }
        if (response.redirected) {
            window.location.assign(response.url);
            throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
        }
        if (!response.ok) {
            const fallback = response.status === 401
                ? "Tu sesi\u00f3n expir\u00f3. Inicia sesi\u00f3n de nuevo."
                : response.status === 403
                    ? "La solicitud fue rechazada por permisos o por la protecci\u00f3n CSRF."
                    : "No se pudo completar la operaci\u00f3n.";
            const error = new Error(payload.error || fallback);
            error.payload = payload;
            throw error;
        }
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

    function formatBytes(bytes) {
        if (!bytes) return "0 B";
        const units = ["B", "KB", "MB", "GB"];
        const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
        return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
    }

    async function loadFolders() {
        const result = await api("/archivos/api/carpetas/");
        folders = result.carpetas;
        const select = $("#fileFolderFilter");
        if (!select) return;
        const selected = select.value;
        select.replaceChildren(new Option("Todas las carpetas", ""));
        folders.forEach((folder) => select.add(new Option(folder.nombre, folder.id)));
        select.value = selected;
    }

    async function loadFiles() {
        const params = new URLSearchParams();
        if ($("#fileProjectFilter")?.value) params.set("proyecto", $("#fileProjectFilter").value);
        if ($("#fileFolderFilter")?.value) params.set("carpeta", $("#fileFolderFilter").value);
        if ($("#fileSearchInput")?.value.trim()) params.set("buscar", $("#fileSearchInput").value.trim());
        try {
            const result = await api(`/archivos/api/${params.size ? `?${params}` : ""}`);
            academicFiles = result.archivos;
            fileFolders = result.carpeta_por_archivo || {};
            fileManagement = result.puede_administrar_por_archivo || {};
            renderFiles();
        } catch (error) { notify(error.message, true); }
    }

    function renderFiles() {
        const list = $("#academicFileList");
        if (!list) return;
        list.replaceChildren();
        if (!academicFiles.length) list.appendChild(make("p", "empty-state", "No hay archivos disponibles en esta vista."));
        let used = 0;
        academicFiles.forEach((file) => {
            used += file.tamano;
            const card = make("article", "file-card");
            const ext = file.nombre.split(".").pop().toUpperCase();
            card.appendChild(make("div", `file-icon ${ext.toLowerCase()}`, ext));
            card.appendChild(make("strong", "", file.nombre));
            card.appendChild(make("span", "", `${formatBytes(file.tamano)} · ${dateLabel(file.fecha_subida.slice(0, 10))}`));
            if (file.proyecto_id) card.appendChild(make("span", "", `Proyecto: ${projects.find((p) => p.id === file.proyecto_id)?.nombre || "Compartido"}`));
            const link = make("a", "text-button", "Descargar");
            link.href = `${file.descarga}?inline=1`;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.setAttribute("aria-label", `Abrir ${file.nombre} en una pestaña nueva`);
            card.appendChild(link);
            const folder = fileFolders[String(file.id)];
            if (folder?.nombre) card.appendChild(make("span", "", `Carpeta: ${folder.nombre}`));
            if (fileManagement[String(file.id)]) {
            const moveTo = document.createElement("select");
            moveTo.setAttribute("aria-label", `Mover ${file.nombre} a una carpeta`);
            moveTo.add(new Option("Sin carpeta", ""));
            folders.forEach((item) => moveTo.add(new Option(item.nombre, item.id)));
            moveTo.value = folder?.id ? String(folder.id) : "";
            const move = make("button", "text-button", "Mover");
            move.type = "button";
            move.addEventListener("click", async () => {
                const body = new FormData(); body.append("carpeta", moveTo.value);
                try {
                    const response = await fetch(`/archivos/api/${file.id}/carpeta/`, { method: "POST", headers: { "X-CSRFToken": csrf, Accept: "application/json" }, body });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || "No se pudo mover el archivo.");
                    notify("Archivo movido correctamente."); await loadFiles();
                } catch (error) { notify(error.message, true); }
            });
            card.append(moveTo, move);
            const remove = make("button", "text-button danger-text", "Eliminar");
            remove.type = "button";
            remove.addEventListener("click", async () => {
                if (!window.confirm(`¿Eliminar ${file.nombre}?`)) return;
                try {
                    const response = await fetch(`/archivos/api/${file.id}/eliminar/`, { method: "DELETE", headers: { "X-CSRFToken": csrf, Accept: "application/json" } });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || "No se pudo eliminar el archivo.");
                    notify("Archivo eliminado correctamente."); await loadFiles();
                } catch (error) { notify(error.message, true); }
            });
            card.appendChild(remove);
            }
            list.appendChild(card);
        });
        $("#storageUsage")?.replaceChildren(document.createTextNode(`${formatBytes(used)} en esta vista`));
    }

    async function attachExisting(endpoint) {
        try {
            const available = await api("/archivos/api/");
            const files = available.archivos.filter((file) => available.puede_administrar_por_archivo?.[String(file.id)]);
            if (!files.length) { notify("Primero sube archivos a tu biblioteca.", true); return; }
            const choice = window.prompt(`Escribe uno o varios números separados por coma para adjuntar:\n${files.map((file, i) => `${i + 1}. ${file.nombre}`).join("\n")}`);
            if (choice === null) return;
            const selected = choice.split(",").map((item) => Number(item.trim()) - 1);
            if (!selected.length || selected.some((index) => !files[index])) { notify("Selecciona números válidos.", true); return; }
            const unique = [...new Set(selected)].map((index) => files[index]);
            if (!window.confirm(`Adjuntar ${unique.length} archivo(s) seleccionado(s)?`)) return;
            for (const file of unique) await api(endpoint, "POST", { archivo_id: file.id });
            notify(unique.length === 1 ? "Archivo adjuntado correctamente." : "Archivos adjuntados correctamente.");
            await Promise.all([loadTasks(), loadProjects()]);
            loadActivity();
        } catch (error) { notify(error.message, true); }
    }

    function appendAttachments(container, files = [], endpoint = "") {
        files.forEach((file) => {
            const row = make("div", "attachment-row");
            const info = make("div", "attachment-info");
            info.appendChild(make("strong", "", file.nombre));
            info.appendChild(make("small", "", `${file.extension || file.tipo || "Archivo"} · ${formatBytes(file.tamano || 0)}${file.fecha_subida ? ` · ${new Date(file.fecha_subida).toLocaleDateString("es-AR")}` : ""}`));
            const link = make("a", "text-button", "Abrir");
            link.href = file.abrir;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            row.append(info, link);
            const download = make("a", "text-button", "Descargar");
            download.href = file.descarga;
            row.appendChild(download);
            if (endpoint && file.puede_quitar) {
                const remove = make("button", "text-button danger-text", "Quitar");
                remove.type = "button";
                remove.addEventListener("click", async () => {
                    try { await api(endpoint, "DELETE", { archivo_id: file.id }); notify("Adjunto quitado."); await Promise.all([loadTasks(), loadProjects()]); }
                    catch (error) { notify(error.message, true); }
                });
                row.appendChild(remove);
            }
            container.appendChild(row);
        });
    }

    async function loadActivity() {
        const list = $("#recentActivityList");
        if (!list) return;
        try {
            const rows = (await api("/api/actividad/")).actividades;
            list.replaceChildren();
            if (!rows.length) { list.appendChild(make("p", "empty-state", "Todavía no hay actividad.")); return; }
            rows.forEach((row) => {
                const item = make("div", "activity");
                item.appendChild(make("div", "activity-icon", "•"));
                const info = make("div");
                info.appendChild(make("strong", "", row.descripcion));
                info.appendChild(make("small", "", `${row.tipo} · ${new Date(row.fecha).toLocaleString("es-AR")}`));
                if (row.tarea_id) {
                    const openTaskLink = make("button", "text-button", "Ver tarea");
                    openTaskLink.type = "button";
                    openTaskLink.addEventListener("click", () => openTaskInDashboard(row.tarea_id));
                    info.appendChild(openTaskLink);
                } else if (row.archivo_id) {
                    const openFile = make("a", "text-button", "Abrir archivo");
                    openFile.href = `/archivos/api/${row.archivo_id}/descargar/?inline=1`;
                    openFile.target = "_blank";
                    openFile.rel = "noopener noreferrer";
                    info.appendChild(openFile);
                } else if (row.proyecto_id) {
                    info.appendChild(make("small", "", `Proyecto #${row.proyecto_id}`));
                }
                item.appendChild(info); list.appendChild(item);
            });
        } catch (error) { notify(error.message, true); }
    }

    async function loadNotifications(show = false) {
        try {
            const result = await api("/api/notificaciones/");
            const dot = $("#notificationBtn .notification-dot");
            if (dot) dot.hidden = result.no_leidas === 0;
            if (!show) return;
            const unread = result.notificaciones.filter((item) => !item.leida);
            if (!unread.length) { notify("No tienes notificaciones nuevas."); return; }
            const selected = window.prompt(`Notificaciones nuevas:\n${unread.map((item, i) => `${i + 1}. ${item.mensaje}`).join("\n")}\n\nEscribe un número para abrir la tarea relacionada.`);
            await api("/api/notificaciones/", "PATCH", { ids: unread.map((item) => item.id) });
            if (dot) dot.hidden = true;
            const notification = unread[Number(selected) - 1];
            const taskId = notification?.url.match(/\/tareas\/api\/(\d+)\//)?.[1];
            if (taskId) {
                openTaskInDashboard(taskId);
            }
        } catch (error) { notify(error.message, true); }
    }

    async function loadDocuments() {
        const requestId = ++documentListRequest;
        try {
            const result = await api("/documentos/api/");
            if (requestId !== documentListRequest) return;
            academicDocuments = result.documentos;
            renderDocuments();
        } catch (error) {
            if (requestId === documentListRequest) notify(error.message, true);
        }
    }

    function renderDocuments() {
        const list = $("#academicDocumentList");
        if (!list) return;
        list.replaceChildren();
        if (!academicDocuments.length) list.appendChild(make("p", "empty-state", "Todavía no hay documentos guardados."));
        academicDocuments.forEach((documento) => {
            const card = make("article", "document-card");
            card.appendChild(make("div", "document-icon", "📝"));
            const summary = make("div");
            summary.appendChild(make("strong", "", documento.titulo));
            summary.appendChild(make("span", "", `${documento.proyecto || "Documento personal"} · Guardado ${dateLabel(documento.fecha_actualizacion.slice(0, 10))}`));
            card.appendChild(summary);
            card.appendChild(make("span", "collaborators", documento.colaboradores.map((person) => person.nombre).join(", ")));
            const open = make("button", "text-button", documento.puede_editar ? "Abrir y editar" : "Ver");
            open.type = "button";
            open.addEventListener("click", () => openDocument(documento));
            card.appendChild(open);
            list.appendChild(card);
        });
    }

    const documentModal = $("#documentModal");
    function applyDocumentToEditor(documento) {
        editingDocument = documento;
        $("#documentModalTitle").textContent = documento ? documento.titulo : "Nuevo documento";
        $("#documentTitleInput").value = documento?.titulo || "";
        $("#documentContentInput").value = documento?.contenido || "";
        $("#documentProjectInput").value = documento?.proyecto_id || "";
        $("#documentProjectInput").disabled = Boolean(documento);
        $("#documentTitleInput").readOnly = Boolean(documento && !documento.puede_editar);
        $("#documentContentInput").readOnly = Boolean(documento && !documento.puede_editar);
        $("#saveDocumentBtn").hidden = Boolean(documento && !documento.puede_editar);
        $("#saveDocumentBtn").disabled = documentSaveInFlight || Boolean(documento && !documento.puede_editar);
        $("#deleteDocumentBtn").hidden = !documento || !documento.puede_eliminar;
        $("#deleteDocumentBtn").disabled = documentSaveInFlight;
        $("#documentVersionLabel").textContent = documento ? `Version ${documento.version}` : "";
    }

    function closeDocument() {
        documentSession += 1;
        documentModal?.classList.remove("show");
    }

    async function openDocument(documento = null) {
        const session = ++documentSession;
        documentConflictPending = false;
        documentConflictVersion = null;
        latestConflictDocument = null;
        $("#documentFormError").textContent = "";
        $("#documentConflict").hidden = true;
        $("#documentRestoreVersionBtn").hidden = true;
        applyDocumentToEditor(documento ? { ...documento } : null);
        documentModal.classList.add("show");
        if (!documento) return;

        $("#saveDocumentBtn").disabled = true;
        try {
            const result = await api(`/documentos/api/${documento.id}/`);
            if (session !== documentSession) return;
            applyDocumentToEditor(result.documento);
        } catch (error) {
            if (session !== documentSession) return;
            $("#saveDocumentBtn").hidden = true;
            $("#documentFormError").textContent = error.message;
        }
    }

    async function saveDocument() {
        if (documentSaveInFlight || (editingDocument && !editingDocument.puede_editar)) return;
        const session = documentSession;
        const documentAtStart = editingDocument ? { ...editingDocument } : null;
        let version = documentAtStart?.version;
        if (documentConflictPending) {
            if (!window.confirm("Revisaste la version guardada. Quieres guardar tu borrador sobre esa version?")) return;
            version = documentConflictVersion;
        }
        const payload = { titulo: $("#documentTitleInput").value.trim(), contenido: $("#documentContentInput").value };
        const project = $("#documentProjectInput").value;
        if (!documentAtStart && project) payload.proyecto = Number(project);
        if (documentAtStart) payload.version = version;

        documentSaveInFlight = true;
        $("#saveDocumentBtn").disabled = true;
        $("#deleteDocumentBtn").disabled = true;
        try {
            await (documentAtStart
                ? api(`/documentos/api/${documentAtStart.id}/`, "PATCH", payload)
                : api("/documentos/api/", "POST", payload));
            documentConflictPending = false;
            documentConflictVersion = null;
            latestConflictDocument = null;
            await loadDocuments();
            if (session === documentSession && editingDocument?.id === documentAtStart?.id) closeDocument();
            notify("Documento guardado.");
        } catch (error) {
            if (session !== documentSession) return;
            if (error.payload?.conflicto && error.payload.documento) {
                latestConflictDocument = error.payload.documento;
                documentConflictVersion = latestConflictDocument.version;
                documentConflictPending = true;
                $("#documentVersionLabel").textContent = `Version guardada ${documentConflictVersion}`;
                $("#documentConflictContent").textContent = `Titulo: ${latestConflictDocument.titulo}\n\n${latestConflictDocument.contenido}`;
                $("#documentConflict").hidden = false;
                $("#documentRestoreVersionBtn").hidden = false;
                $("#documentFormError").textContent = "Tu borrador sigue en el editor. Compara ambas versiones o carga la guardada antes de decidir.";
            } else {
                $("#documentFormError").textContent = error.message;
            }
        } finally {
            documentSaveInFlight = false;
            $("#saveDocumentBtn").disabled = Boolean(editingDocument && !editingDocument.puede_editar);
            $("#deleteDocumentBtn").disabled = false;
        }
    }

    async function deleteDocument() {
        if (documentSaveInFlight || !editingDocument || !window.confirm(`Eliminar "${editingDocument.titulo}"?`)) return;
        const session = documentSession;
        const documentAtStart = { ...editingDocument };
        documentSaveInFlight = true;
        $("#deleteDocumentBtn").disabled = true;
        $("#saveDocumentBtn").disabled = true;
        try {
            await api(`/documentos/api/${documentAtStart.id}/`, "DELETE", {});
            await loadDocuments();
            if (session === documentSession && editingDocument?.id === documentAtStart.id) closeDocument();
            notify("Documento eliminado.");
        } catch (error) {
            if (session === documentSession) $("#documentFormError").textContent = error.message;
        } finally {
            documentSaveInFlight = false;
            $("#saveDocumentBtn").disabled = Boolean(editingDocument && !editingDocument.puede_editar);
            $("#deleteDocumentBtn").disabled = false;
        }
    }

    function restoreLatestDocumentVersion() {
        if (!latestConflictDocument || !window.confirm("Cargar la version del servidor y descartar el borrador actual?")) return;
        applyDocumentToEditor(latestConflictDocument);
        documentConflictPending = false;
        documentConflictVersion = null;
        latestConflictDocument = null;
        $("#documentConflict").hidden = true;
        $("#documentRestoreVersionBtn").hidden = true;
        $("#documentFormError").textContent = "";
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

    function openTaskInDashboard(taskId) {
        const projectTask = projects.some((project) => project.tareas.some((task) => task.id === Number(taskId)));
        const section = projectTask ? "proyectos" : "tareas";
        document.querySelector(`.nav-item[data-section="${section}"]`)?.click();
        window.setTimeout(() => document.getElementById(`task-${taskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
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
    const taskDetailModal = $("#taskDetailModal");
    const projectDetailModal = $("#projectDetailModal");
    function closeTaskModal() { taskModal?.classList.remove("show"); }
    function closeProjectModal() { projectModal?.classList.remove("show"); }
    function closeTaskDetail() { taskDetailModal?.classList.remove("show"); }
    function closeProjectDetail() { projectDetailModal?.classList.remove("show"); }

    async function openTaskDetails(taskId) {
        try {
            const task = (await api(`${taskUrl}${taskId}/`)).tarea;
            const deliveryResult = await api(`${taskUrl}${taskId}/entregas/`);
            const content = $("#taskDetailContent");
            content.replaceChildren();
            const taskTitle = make("h2", "", task.titulo);
            taskTitle.id = "taskDetailTitle";
            content.appendChild(taskTitle);
            content.appendChild(make("p", "", task.descripcion || "Sin descripción."));
            const project = projects.find((item) => item.id === task.proyecto_id);
            content.appendChild(make("p", "", "Materia: No especificada"));
            content.appendChild(make("p", "", `Creada: ${dateLabel(task.fecha_creacion?.slice(0, 10))} · Entrega: ${dateLabel(task.fecha_vencimiento)} · Prioridad: ${task.prioridad} · Estado: ${states.find(([value]) => value === task.estado)?.[1] || task.estado}${project ? ` · Proyecto: ${project.nombre}` : ""}`));
            content.appendChild(make("h3", "", "Archivos adjuntos"));
            const files = make("div", "detail-attachments");
            appendAttachments(files, task.archivos_adjuntos, `${taskUrl}${task.id}/archivos/`);
            if (!task.archivos_adjuntos.length) files.appendChild(make("p", "empty-state", "No hay archivos adjuntos."));
            content.appendChild(files);
            content.appendChild(make("h3", "", "Entrega del alumno"));
            if (deliveryResult.entregas.length) deliveryResult.entregas.forEach((delivery) => {
                content.appendChild(make("p", "", `${delivery.estado} · ${new Date(delivery.fecha_entrega).toLocaleString("es-AR")}${delivery.observaciones ? ` · ${delivery.observaciones}` : ""}`));
                const link = make("a", "text-button", `Descargar ${delivery.nombre}`); link.href = delivery.descarga; content.appendChild(link);
                if (delivery.correccion) {
                    const correction = delivery.correccion;
                    content.appendChild(make("p", "", `Estado de revisión: ${correction.estado} · Fecha de devolución: ${new Date(correction.fecha).toLocaleString("es-AR")}`));
                    if (correction.calificacion !== "") content.appendChild(make("p", "", `Calificación: ${correction.calificacion}/${document.body.dataset.gradeMax}`));
                    if (correction.comentario) content.appendChild(make("p", "", correction.comentario));
                } else content.appendChild(make("p", "empty-state", "La entrega aún no tiene devolución docente."));
            });
            else if (task.puede_entregar) {
                const submit = make("form", "detail-delivery-form"), file = document.createElement("input"), note = document.createElement("textarea"), button = make("button", "primary-button", "Enviar entrega");
                file.type = "file"; file.required = true; note.placeholder = "Observaciones (opcional)"; note.maxLength = 20000; button.type = "submit";
                submit.append(file, note, button);
                submit.addEventListener("submit", async (event) => {
                    event.preventDefault(); if (!file.files.length) return;
                    const data = new FormData(); data.append("archivo", file.files[0]); data.append("observaciones", note.value);
                    try { await fetch(`${taskUrl}${task.id}/entregas/`, {method:"POST", headers:{"X-CSRFToken":csrf, Accept:"application/json"}, body:data}).then(async (response) => { const result=await response.json(); if(!response.ok) throw new Error(result.error || "No se pudo enviar la entrega."); return result; }); await openTaskDetails(task.id); notify("Entrega enviada."); }
                    catch(error) { notify(error.message, true); }
                });
                content.appendChild(submit);
            } else content.appendChild(make("p", "empty-state", "No hay una entrega registrada."));
            if (task.puede_adjuntar) {
                const attach = make("button", "secondary-button", "Adjuntar archivos");
                attach.type = "button";
                attach.addEventListener("click", async () => { await attachExisting(`${taskUrl}${task.id}/archivos/`); await openTaskDetails(task.id); });
                content.appendChild(attach);
            }
            content.appendChild(make("h3", "", "Devoluciones y calificaciones"));
            if (!task.devoluciones.length) content.appendChild(make("p", "empty-state", "Todavía no hay devoluciones para esta tarea."));
            task.devoluciones.forEach((entry) => {
                const item = make("article", "project-feedback-entry");
                item.appendChild(make("strong", "", `${entry.autor} · ${new Date(entry.fecha).toLocaleString("es-AR")}`));
                if (entry.comentario) item.appendChild(make("p", "", entry.comentario));
                if (entry.calificacion !== "") item.appendChild(make("p", "", `Calificación: ${entry.calificacion}/10`));
                content.appendChild(item);
            });
            taskDetailModal.classList.add("show");
        } catch (error) { notify(error.message, true); }
    }

    function openProjectDetails(project) {
        const content = $("#projectDetailContent");
        content.replaceChildren();
        const projectTitle = make("h2", "", project.nombre);
        projectTitle.id = "projectDetailTitle";
        content.appendChild(projectTitle);
        content.appendChild(make("p", "", project.descripcion || "Sin descripción."));
        content.appendChild(make("p", "", `Entrega: ${dateLabel(project.fecha_entrega)} · Progreso: ${project.progreso}%`));
        content.appendChild(make("p", "", `Integrantes: ${project.integrantes.map((member) => member.nombre).join(", ")}`));
        content.appendChild(make("h3", "", "Archivos del proyecto"));
        appendAttachments(content, project.archivos_adjuntos, project.puede_adjuntar ? `${projectUrl}${project.id}/archivos/` : "");
        if (!project.archivos_adjuntos.length) content.appendChild(make("p", "empty-state", "No hay archivos adjuntos al proyecto."));
        content.appendChild(make("h3", "", "Tareas del equipo"));
        project.tareas.forEach((task) => {
            const row = make("article", "project-feedback-entry");
            row.appendChild(make("strong", "", task.titulo));
            row.appendChild(make("p", "", `${task.estado} · ${task.prioridad} · Entrega: ${dateLabel(task.fecha_vencimiento)}`));
            appendAttachments(row, task.archivos_adjuntos);
            const open = make("button", "text-button", "Ver tarea");
            open.type = "button";
            open.addEventListener("click", () => { closeProjectDetail(); openTaskDetails(task.id); });
            row.appendChild(open);
            content.appendChild(row);
        });
        content.appendChild(make("h3", "", "Devoluciones generales del proyecto"));
        const projectEntries = project.devoluciones.filter((entry) => !entry.tarea_id && !entry.documento_id);
        if (!projectEntries.length) content.appendChild(make("p", "empty-state", "Todavía no hay devoluciones generales."));
        projectEntries.forEach((entry) => {
            const item = make("article", "project-feedback-entry");
            item.appendChild(make("strong", "", `${entry.autor} · ${new Date(entry.fecha).toLocaleString("es-AR")}`));
            if (entry.comentario) item.appendChild(make("p", "", entry.comentario));
            if (entry.calificacion !== "") item.appendChild(make("p", "", `Calificación: ${entry.calificacion}/10`));
            content.appendChild(item);
        });
        projectDetailModal.classList.add("show");
    }

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
                card.id = `task-${task.id}`;
                card.appendChild(make("strong", "", task.titulo));
                if (task.descripcion) card.appendChild(make("p", "", task.descripcion));
                card.appendChild(make("span", "card-date", `${dateLabel(task.fecha_vencimiento)} · Prioridad ${task.prioridad}`));
                const actions = make("div", "task-card-actions");
                const view = make("button", "text-button", "Ver tarea");
                view.type = "button";
                view.addEventListener("click", () => openTaskDetails(task.id));
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
                actions.append(view, stateSelect);
                if (task.puede_editar !== false) actions.append(edit, remove);
                if (task.puede_adjuntar) {
                    const attach = make("button", "text-button", "Adjuntar archivos");
                    attach.type = "button";
                    attach.addEventListener("click", () => attachExisting(`${taskUrl}${task.id}/archivos/`));
                    actions.appendChild(attach);
                }
                appendAttachments(card, task.archivos_adjuntos, `${taskUrl}${task.id}/archivos/`);
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
        $("#priorityInput").disabled = true;
        $("#taskStateInput").value = task?.estado || "pendiente";
        $("#taskAttachmentInput").value = "";
        $("#taskFormError").textContent = "";
        $("#deleteTaskBtn").hidden = !task;
        taskModal.classList.add("show");
        $("#taskInput").focus();
    }

    $("#taskDueDate")?.addEventListener("change", () => {
        const value = $("#taskDueDate").value;
        if (!value) { $("#priorityInput").value = "media"; return; }
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const due = new Date(`${value}T00:00:00`);
        const days = Math.floor((due - today) / 86400000);
        $("#priorityInput").value = days > 20 ? "baja" : days >= 5 ? "media" : "alta";
    });

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
            const wasEditing = Boolean(editingTask);
            const result = editingTask
                ? await api(`${taskUrl}${editingTask.id}/`, "PATCH", data)
                : await api(taskUrl, "POST", data);
            const taskId = editingTask?.id || result.tarea.id;
            if (!wasEditing) editingTask = result.tarea;
            const selectedFiles = [...($("#taskAttachmentInput")?.files || [])];
            for (const [index, file] of selectedFiles.entries()) {
                const form = new FormData();
                form.append("archivo", file);
                form.append("tarea", String(taskId));
                const response = await fetch("/archivos/api/", { method: "POST", headers: { "X-CSRFToken": csrf, Accept: "application/json" }, body: form });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload.error || `No se pudo adjuntar ${file.name}.`);
                const remaining = selectedFiles.slice(index + 1);
                const pending = new DataTransfer();
                remaining.forEach((item) => pending.items.add(item));
                $("#taskAttachmentInput").files = pending.files;
            }
            closeTaskModal();
            await Promise.all([loadTasks(), loadProjects()]);
            notify(wasEditing ? "Tarea actualizada." : "Tarea creada.");
            loadActivity();
        } catch (error) { $("#taskFormError").textContent = error.message; }
    }

    async function deleteTask(task) {
        if (!window.confirm(`¿Eliminar la tarea “${task.titulo}”?`)) return;
        try {
            await api(`${taskUrl}${task.id}/`, "DELETE", {});
            await Promise.all([loadTasks(), loadProjects()]);
            notify("Tarea eliminada.");
            loadActivity();
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
            const viewProject = make("button", "text-button", "Ver proyecto");
            viewProject.type = "button";
            viewProject.addEventListener("click", () => openProjectDetails(project));
            card.appendChild(viewProject);
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
            if (project.puede_adjuntar) {
                const edit = make("button", "text-button", "Editar proyecto");
                edit.type = "button";
                edit.addEventListener("click", () => openProject(project));
                actions.appendChild(edit);
            }
            card.appendChild(actions);
            appendAttachments(card, project.archivos_adjuntos, project.puede_adjuntar ? `${projectUrl}${project.id}/archivos/` : "");
            if (project.puede_editar) {
                const attachProject = make("button", "text-button", "Adjuntar archivos al proyecto");
                attachProject.type = "button";
                attachProject.addEventListener("click", () => attachExisting(`${projectUrl}${project.id}/archivos/`));
                card.appendChild(attachProject);
            }

            const taskList = make("div", "project-task-list");
            taskList.appendChild(make("h4", "", "Tareas del equipo"));
            if (!project.tareas.length) taskList.appendChild(make("p", "empty-state", "Todavía no hay tareas."));
            project.tareas.forEach((task) => {
                const row = make("div", "project-task-row");
                row.id = `task-${task.id}`;
                const details = make("div");
                details.appendChild(make("strong", "", task.titulo));
                details.appendChild(make("small", "", `${states.find(([value]) => value === task.estado)?.[1] || task.estado} · ${task.prioridad} · ${dateLabel(task.fecha_vencimiento)}`));
                row.appendChild(details);
                const viewTask = make("button", "text-button", "Ver tarea");
                viewTask.type = "button";
                viewTask.addEventListener("click", () => openTaskDetails(task.id));
                row.appendChild(viewTask);

                const deliveryPanel = make("div", "group-delivery-panel");
                deliveryPanel.appendChild(make("strong", "", "Entrega grupal"));
                if (task.archivos_adjuntos?.length) {
                    deliveryPanel.appendChild(make("strong", "", "Archivos adjuntos del alumno"));
                    appendAttachments(deliveryPanel, task.archivos_adjuntos, `${taskUrl}${task.id}/archivos/`);
                }
                if (task.entregas?.length) {
                    task.entregas.forEach((delivery) => {
                        const info = make("p", "", `Entrega #${delivery.id} · ${delivery.alumno} · ${dateLabel(delivery.fecha_entrega.slice(0, 10))} · ${delivery.estado}`);
                        deliveryPanel.appendChild(info);
                        const download = make("a", "text-button", `Descargar ${delivery.nombre}`);
                        download.href = delivery.descarga;
                        deliveryPanel.appendChild(download);
                        if (/\.(pdf|png|jpe?g)$/i.test(delivery.nombre)) {
                            const preview = make("a", "text-button", "Abrir en el navegador");
                            preview.href = `${delivery.descarga}?inline=1`;
                            preview.target = "_blank";
                            preview.rel = "noopener noreferrer";
                            deliveryPanel.appendChild(preview);
                        }
                    });
                    deliveryPanel.appendChild(make("small", "", "La entrega queda disponible para todo el grupo."));
                } else {
                    deliveryPanel.appendChild(make("p", "", "El grupo todavía no realizó la entrega."));
                    const file = document.createElement("input");
                    file.type = "file";
                    file.accept = ".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg";
                    file.setAttribute("aria-label", `Archivo para entregar: ${task.titulo}`);
                    const submit = make("button", "text-button", "Entregar archivo por el grupo");
                    submit.type = "button";
                    submit.disabled = true;
                    file.addEventListener("change", () => { submit.disabled = !file.files?.length; });
                    submit.addEventListener("click", async () => {
                        const uploaded = file.files?.[0];
                        if (!uploaded) return;
                        submit.disabled = true;
                        try {
                            const body = new FormData();
                            body.append("archivo", uploaded);
                            const response = await fetch(`${taskUrl}${task.id}/entregas/`, {
                                method: "POST",
                                headers: { Accept: "application/json", "X-CSRFToken": csrf },
                                body,
                            });
                            let result = {};
                            try { result = await response.json(); } catch (_) { /* error genérico */ }
                            if (response.status === 409) {
                                await loadProjects();
                                notify(result.error || "El grupo ya realizó la entrega.", true);
                                return;
                            }
                            if (!response.ok) throw new Error(result.error || "No se pudo entregar el archivo.");
                            await loadProjects();
                            notify("Entrega grupal registrada.");
                        } catch (error) {
                            notify(error.message, true);
                            submit.disabled = !file.files?.length;
                        }
                    });
                    deliveryPanel.append(file, submit);
                }
                if (task.evaluacion_grupal) {
                    const evaluation = task.evaluacion_grupal;
                    deliveryPanel.appendChild(make("p", "", `Evaluación grupal: ${evaluation.calificacion || "Sin nota"}${evaluation.comentario ? ` · ${evaluation.comentario}` : ""}`));
                }
                const personalEvaluation = task.evaluacion_individual;
                if (personalEvaluation) {
                    deliveryPanel.appendChild(make("p", "", `Tu evaluación individual: ${personalEvaluation.calificacion || "Sin nota"}${personalEvaluation.comentario ? ` · ${personalEvaluation.comentario}` : ""}`));
                }
                row.appendChild(deliveryPanel);
                const editTask = make("button", "text-button", "Editar");
                editTask.type = "button";
                editTask.addEventListener("click", () => openTask(task));
                row.appendChild(editTask);
                taskList.appendChild(row);
            });
            card.appendChild(taskList);
            const projectFeedback = project.devoluciones.filter((entry) => !entry.tarea_id && !entry.documento_id);
            if (projectFeedback.length) {
                const feedback = make("div", "project-feedback-history");
                feedback.appendChild(make("h4", "", "Devoluciones docentes"));
                projectFeedback.forEach((entry) => {
                    const item = make("article", "project-feedback-entry");
                    const label = entry.tipo === "grupal" ? "Evaluación grupal"
                        : entry.tipo === "individual" ? `Evaluación individual · ${entry.alumno}`
                            : "Registro histórico";
                    item.appendChild(make("strong", "", label));
                    item.appendChild(make("strong", "", `${entry.autor} · ${entry.fecha.slice(0, 10)}`));
                    if (entry.tarea || entry.documento) item.appendChild(make("small", "", `Sobre ${entry.tarea || entry.documento}`));
                    if (entry.comentario) item.appendChild(make("p", "", entry.comentario));
                    if (entry.calificacion) item.appendChild(make("p", "", `Calificación: ${entry.calificacion}/10`));
                    feedback.appendChild(item);
                });
                card.appendChild(feedback);
            }
            list.appendChild(card);
        });
        $("#projectCountText")?.replaceChildren(document.createTextNode(`${projects.length} proyectos grupales`));
    }

    async function loadProjects() {
        try {
            projects = (await api(projectUrl)).proyectos;
            await Promise.all(projects.flatMap((project) => project.tareas.map(async (task) => {
                const [deliveries, evaluations] = await Promise.all([
                    api(`${taskUrl}${task.id}/entregas/`),
                    api(`${taskUrl}${task.id}/evaluaciones/`),
                ]);
                task.entregas = deliveries.entregas;
                task.evaluacion_grupal = evaluations.grupal;
                task.evaluacion_individual = evaluations.individuales[0] || null;
            })));
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
            loadActivity();
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
    taskDetailModal?.addEventListener("click", (event) => { if (event.target === taskDetailModal) closeTaskDetail(); });
    projectDetailModal?.addEventListener("click", (event) => { if (event.target === projectDetailModal) closeProjectDetail(); });
    $$('[data-close-task-detail]').forEach((button) => button.addEventListener("click", closeTaskDetail));
    $$('[data-close-project-detail]').forEach((button) => button.addEventListener("click", closeProjectDetail));
    ["#filterTaskStatus", "#filterTaskPriority", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => {
        $(selector)?.addEventListener("change", loadTasks);
    });
    $("#clearTaskFilters")?.addEventListener("click", () => {
        ["#filterTaskStatus", "#filterTaskPriority", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => { if ($(selector)) $(selector).value = ""; });
        loadTasks();
    });
    $("#notificationBtn")?.addEventListener("click", () => loadNotifications(true));

    $("#uploadFileBtn")?.addEventListener("click", () => $("#academicFileInput")?.click());
    $("#academicFileInput")?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        const data = new FormData();
        data.append("archivo", file);
        if ($("#fileProjectFilter")?.value) data.append("proyecto", $("#fileProjectFilter").value);
        if ($("#fileFolderFilter")?.value) data.append("carpeta", $("#fileFolderFilter").value);
        try {
            const response = await fetch("/archivos/api/", { method: "POST", headers: { "X-CSRFToken": csrf, Accept: "application/json" }, body: data });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No se pudo subir el archivo.");
            notify("Archivo subido.");
            await loadFiles();
            loadActivity();
        } catch (error) { notify(error.message, true); }
        event.target.value = "";
    });
    $("#fileProjectFilter")?.addEventListener("change", () => {
        const projectSelect = $("#documentProjectInput");
        if (projectSelect) projectSelect.value = "";
        loadFiles();
    });
    $("#fileFolderFilter")?.addEventListener("change", loadFiles);
    let fileSearchTimer;
    $("#fileSearchInput")?.addEventListener("input", () => { clearTimeout(fileSearchTimer); fileSearchTimer = setTimeout(loadFiles, 180); });
    $("#newFolderBtn")?.addEventListener("click", async () => {
        const nombre = window.prompt("Nombre de la carpeta:")?.trim();
        if (!nombre) return;
        const body = new FormData();
        body.append("nombre", nombre);
        try {
            const response = await fetch("/archivos/api/carpetas/", { method: "POST", headers: { "X-CSRFToken": csrf, Accept: "application/json" }, body });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || "No se pudo crear la carpeta.");
            await loadFolders();
            $("#fileFolderFilter").value = String(result.carpeta.id);
            await loadFiles();
            notify("Carpeta creada correctamente.");
        } catch (error) { notify(error.message, true); }
    });
    $("#newDocumentBtn")?.addEventListener("click", () => openDocument());
    $("#saveDocumentBtn")?.addEventListener("click", saveDocument);
    $("#deleteDocumentBtn")?.addEventListener("click", deleteDocument);
    $("#documentRestoreVersionBtn")?.addEventListener("click", restoreLatestDocumentVersion);
    $$('[data-close-document]').forEach((button) => button.addEventListener("click", closeDocument));
    documentModal?.addEventListener("click", (event) => { if (event.target === documentModal) closeDocument(); });

    loadTasks();
    loadProjects().then(() => {
        const fileProject = $("#fileProjectFilter");
        const docProject = $("#documentProjectInput");
        projects.forEach((project) => {
            fileProject?.add(new Option(project.nombre, project.id));
            docProject?.add(new Option(project.nombre, project.id));
        });
        loadFiles();
    });
    loadFolders().then(loadFiles).catch((error) => notify(error.message, true));
    loadDocuments();
    loadActivity();
    loadNotifications();
})();
