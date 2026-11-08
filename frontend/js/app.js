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
    let allPersonalTasks = [];
    let projects = [];
    let students = [];
    let editingTask = null;
    let taskSaveInFlight = false;
    let taskProjectId = null;
    let projectTaskBoardId = null;
    let returningFromProjectTaskBoard = false;
    let projectResourcesId = null;
    let projectResourcesRequest = 0;
    let projectResourcesReturnId = null;
    let contextualDocumentProjectId = null;
    let editingProject = null;
    let projectSaveInFlight = false;
    let academicFiles = [];
    let fileListRequest = 0;
    let folders = [];
    let academicDocuments = [];
    let editingDocument = null;
    let documentConflictPending = false;
    let documentConflictVersion = null;
    let latestConflictDocument = null;
    let documentSession = 0;
    let documentListRequest = 0;
    let taskListRequest = 0;
    let projectListRequest = 0;
    let documentSaveInFlight = false;
    let documentSelectionRange = null;
    let documentLoading = false;
    let documentLoadFailed = false;
    let documentContentInvalid = false;
    let documentEditRevision = 0;
    const richDocumentFormat = "eduflow.rich-text";
    const richDocumentVersion = 1;
    const documentFonts = ["Arial", "Georgia", "Times New Roman", "Verdana", "Tahoma", "Courier New"];
    const documentSizes = [10, 12, 14, 16, 18, 24, 32, 48];
    const maxRichBlocks = 1000;
    const maxRichRuns = 10000;
    const maxRichText = 900000;
    const maxDocumentContent = 1000000;

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
        const requestId = ++fileListRequest;
        const params = new URLSearchParams();
        if ($("#fileProjectFilter")?.value) params.set("proyecto", $("#fileProjectFilter").value);
        if ($("#fileFolderFilter")?.value) params.set("carpeta", $("#fileFolderFilter").value);
        try {
            const result = await api(`/archivos/api/${params.size ? `?${params}` : ""}`);
            if (requestId !== fileListRequest) return;
            academicFiles = result.archivos;
            renderFiles();
        } catch (error) { if (requestId === fileListRequest) notify(error.message, true); }
    }

    function renderFiles() {
        const list = $("#academicFileList");
        if (!list) return;
        list.replaceChildren();
        if (!academicFiles.length) list.appendChild(make("p", "empty-state", "No hay archivos disponibles en esta vista."));
        academicFiles.forEach((file) => {
            const card = make("article", "file-card");
            const ext = file.nombre.split(".").pop().toUpperCase();
            card.appendChild(make("div", `file-icon ${ext.toLowerCase()}`, ext));
            card.appendChild(make("strong", "", file.nombre));
            card.appendChild(make("span", "", `${formatBytes(file.tamano)} · ${dateLabel(file.fecha_subida.slice(0, 10))}`));
            if (file.proyecto_id) card.appendChild(make("span", "", `Proyecto: ${projects.find((p) => p.id === file.proyecto_id)?.nombre || "Compartido"}`));
            const link = make("a", "text-button", "Descargar");
            link.href = file.descarga;
            link.setAttribute("aria-label", `Descargar ${file.nombre}`);
            card.appendChild(link);
            list.appendChild(card);
        });
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
        renderRecentDocuments();
    }

    function renderRecentDocuments() {
        const list = $("#recentDocumentList");
        if (!list) return;
        list.replaceChildren();
        const recent = academicDocuments.slice(0, 3);
        if (!recent.length) {
            list.appendChild(make("p", "empty-state", "Todavía no hay documentos recientes."));
            return;
        }
        recent.forEach((documento) => {
            const item = make("div", "activity");
            item.appendChild(make("div", "activity-icon", "📝"));
            const info = make("div");
            info.appendChild(make("strong", "", documento.titulo));
            info.appendChild(make("span", "", documento.proyecto || "Documento personal"));
            info.appendChild(make("small", "", `Actualizado ${dateLabel(documento.fecha_actualizacion.slice(0, 10))}`));
            item.appendChild(info);
            const open = make("button", "text-button", documento.puede_editar ? "Abrir" : "Ver");
            open.type = "button";
            open.addEventListener("click", () => openDocument(documento));
            item.appendChild(open);
            list.appendChild(item);
        });
    }

    const documentModal = $("#documentModal");
    function hasExactKeys(value, allowed) {
        return value && typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === allowed.length && Object.keys(value).every((key) => allowed.includes(key));
    }

    function richDocumentDepthAllowed(value) {
        const stack = [[value, 1]];
        while (stack.length) {
            const [current, depth] = stack.pop();
            if (depth > 6) return false;
            if (Array.isArray(current)) current.forEach((child) => stack.push([child, depth + 1]));
            else if (current && typeof current === "object") Object.values(current).forEach((child) => stack.push([child, depth + 1]));
        }
        return true;
    }

    function validRichDocument(value) {
        if (!richDocumentDepthAllowed(value) || !hasExactKeys(value, ["format", "version", "blocks"]) || value.format !== richDocumentFormat || value.version !== richDocumentVersion || !Array.isArray(value.blocks) || value.blocks.length < 1 || value.blocks.length > maxRichBlocks) return false;
        let runCount = 0;
        let textLength = 0;
        for (const block of value.blocks) {
            if (!hasExactKeys(block, ["type", "align", "runs"]) || block.type !== "paragraph" || !["left", "center", "right", "justify"].includes(block.align) || !Array.isArray(block.runs) || !block.runs.length) return false;
            runCount += block.runs.length;
            if (runCount > maxRichRuns) return false;
            for (const run of block.runs) {
                if (!hasExactKeys(run, ["text", "bold", "italic", "font", "size"]) || typeof run.text !== "string" || typeof run.bold !== "boolean" || typeof run.italic !== "boolean" || !documentFonts.includes(run.font) || !documentSizes.includes(run.size)) return false;
                textLength += [...run.text].length;
                if (textLength > maxRichText) return false;
            }
        }
        return true;
    }

    function claimsCurrentRichFormat(content) {
        return /^\s*\{/.test(content) && /"format"\s*:\s*"eduflow\.rich-text"/.test(content) && /"version"\s*:\s*1(?:\s*[,}])/.test(content);
    }

    function parseDocumentContent(content) {
        if ([...content].length > maxDocumentContent) throw new Error("El contenido supera el límite permitido.");
        let parsed;
        try {
            parsed = JSON.parse(content || "");
        } catch (_) {
            if (claimsCurrentRichFormat(content)) throw new Error("El documento enriquecido está malformado. El contenido original se conserva para recuperarlo.");
            return { blocks: String(content || "").split("\n").map((text) => ({ type: "paragraph", align: "left", runs: [makeDocumentRun(text)] })) };
        }
        if (!parsed || parsed.format !== richDocumentFormat || parsed.version !== richDocumentVersion) {
            return { blocks: String(content || "").split("\n").map((text) => ({ type: "paragraph", align: "left", runs: [makeDocumentRun(text)] })) };
        }
        if (!validRichDocument(parsed)) throw new Error("El documento enriquecido no cumple el formato permitido. El contenido original se conserva para recuperarlo.");
        return parsed;
    }

    function makeDocumentRun(text, format = {}) {
        return { text, bold: Boolean(format.bold), italic: Boolean(format.italic), font: format.font || "Arial", size: format.size || 16 };
    }

    function renderDocumentContent(content) {
        const editor = $("#documentContentInput");
        try {
            const model = parseDocumentContent(String(content || ""));
            documentContentInvalid = false;
            $("#documentInvalidContent").hidden = true;
            $("#documentInvalidContentText").textContent = "";
            editor.replaceChildren();
            model.blocks.forEach((block) => {
                const paragraph = document.createElement("p");
                paragraph.style.textAlign = block.align;
                (block.runs.length ? block.runs : [makeDocumentRun("")]).forEach((run) => {
                    let node = document.createTextNode(run.text);
                    if (run.italic) { const italic = document.createElement("em"); italic.append(node); node = italic; }
                    if (run.bold) { const bold = document.createElement("strong"); bold.append(node); node = bold; }
                    const span = document.createElement("span");
                    span.style.fontFamily = run.font;
                    span.style.fontSize = `${run.size}px`;
                    span.append(node);
                    paragraph.append(span);
                });
                editor.append(paragraph);
            });
            if (!model.blocks.length) editor.append(document.createElement("p"));
            return true;
        } catch (error) {
            documentContentInvalid = true;
            editor.replaceChildren();
            $("#documentInvalidContentText").textContent = String(content || "");
            $("#documentInvalidContent").hidden = false;
            $("#documentFormError").textContent = error.message;
            return false;
        }
    }

    function serializeDocumentContent() {
        const editor = $("#documentContentInput");
        const blocks = [...editor.childNodes].map((node) => {
            const paragraph = node.nodeType === Node.ELEMENT_NODE && ["P", "DIV"].includes(node.tagName) ? node : null;
            const runs = [];
            const walk = (current, inherited = {}) => {
                if (current.nodeType === Node.TEXT_NODE) {
                    const text = (current.nodeValue || "").replace(/\u200b/g, "");
                    if (!text) return;
                    const last = runs[runs.length - 1];
                    if (last && last.bold === inherited.bold && last.italic === inherited.italic && last.font === inherited.font && last.size === inherited.size) last.text += text;
                    else runs.push(makeDocumentRun(text, inherited));
                    return;
                }
                if (current.nodeType !== Node.ELEMENT_NODE) return;
                const next = { ...inherited };
                if (current.tagName === "B" || current.tagName === "STRONG") next.bold = true;
                if (current.tagName === "I" || current.tagName === "EM") next.italic = true;
                const family = current.style?.fontFamily?.replace(/[\"']/g, "").split(",")[0].trim();
                if (documentFonts.includes(family)) next.font = family;
                const size = Number.parseInt(current.style?.fontSize || "", 10);
                if (documentSizes.includes(size)) next.size = size;
                if (current.tagName === "BR") { runs.push(makeDocumentRun("\n", next)); return; }
                current.childNodes.forEach((child) => walk(child, next));
            };
            (paragraph || node).childNodes.forEach((child) => walk(child));
            if (!runs.length) runs.push(makeDocumentRun(""));
            return { type: "paragraph", align: paragraph && ["left", "center", "right", "justify"].includes(paragraph.style.textAlign) ? paragraph.style.textAlign : "left", runs };
        });
        return JSON.stringify({ format: richDocumentFormat, version: richDocumentVersion, blocks: blocks.length ? blocks : [{ type: "paragraph", align: "left", runs: [makeDocumentRun("")] }] });
    }

    function rememberDocumentSelection() {
        const selection = window.getSelection();
        const editor = $("#documentContentInput");
        if (selection?.rangeCount && editor.contains(selection.anchorNode) && editor.contains(selection.focusNode)) documentSelectionRange = selection.getRangeAt(0).cloneRange();
    }

    function restoreDocumentSelection() {
        const editor = $("#documentContentInput");
        editor.focus();
        if (documentSelectionRange && editor.contains(documentSelectionRange.commonAncestorContainer)) {
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(documentSelectionRange);
        }
    }

    function applyDocumentInlineStyle(property, value) {
        restoreDocumentSelection();
        const selection = window.getSelection();
        if (!selection?.rangeCount) return;
        const range = selection.getRangeAt(0);
        const span = document.createElement("span");
        span.style[property] = value;
        if (range.collapsed) {
            span.append(document.createTextNode("\u200b"));
            range.insertNode(span);
            const next = document.createRange();
            next.setStart(span.firstChild, 1);
            next.collapse(true);
            selection.removeAllRanges();
            selection.addRange(next);
            documentSelectionRange = next.cloneRange();
            return;
        }
        span.append(range.extractContents());
        range.insertNode(span);
        selection.removeAllRanges();
        const next = document.createRange();
        next.selectNodeContents(span);
        selection.addRange(next);
        documentSelectionRange = next.cloneRange();
    }

    function serializeDocumentFromEditor() {
        const editor = $("#documentContentInput");
        editor.addEventListener("paste", (event) => {
            event.preventDefault();
            const text = event.clipboardData?.getData("text/plain") || "";
            document.execCommand("insertText", false, text);
        });
        editor.addEventListener("drop", (event) => {
            event.preventDefault();
            const text = event.dataTransfer?.getData("text/plain") || "";
            document.execCommand("insertText", false, text);
        });
        editor.addEventListener("input", () => {
            documentEditRevision += 1;
            rememberDocumentSelection();
        });
        $("#documentTitleInput").addEventListener("input", () => { documentEditRevision += 1; });
        document.addEventListener("selectionchange", rememberDocumentSelection);
        $$("[data-format]").forEach((button) => button.addEventListener("mousedown", (event) => event.preventDefault()));
        $$("[data-format]").forEach((button) => button.addEventListener("click", () => {
            restoreDocumentSelection();
            document.execCommand(button.dataset.format, false);
            rememberDocumentSelection();
        }));
        $$("[data-align]").forEach((button) => button.addEventListener("mousedown", (event) => event.preventDefault()));
        $$("[data-align]").forEach((button) => button.addEventListener("click", () => {
            restoreDocumentSelection();
            const selection = window.getSelection();
            const editor = $("#documentContentInput");
            let block = selection?.anchorNode?.nodeType === Node.ELEMENT_NODE ? selection.anchorNode : selection?.anchorNode?.parentElement;
            while (block && block !== editor && !["P", "DIV"].includes(block.tagName)) block = block.parentElement;
            if (!block || block === editor) { block = document.createElement("p"); block.append(document.createElement("br")); editor.append(block); }
            block.style.textAlign = button.dataset.align;
            rememberDocumentSelection();
        }));
        $("#documentFontFamily")?.addEventListener("change", (event) => applyDocumentInlineStyle("fontFamily", event.target.value));
        $("#documentFontSize")?.addEventListener("change", (event) => applyDocumentInlineStyle("fontSize", `${Number(event.target.value)}px`));
    }

    function updateDocumentControls() {
        const lacksPermission = Boolean(editingDocument && !editingDocument.puede_editar);
        const locked = documentLoading || documentSaveInFlight || documentLoadFailed || documentContentInvalid || lacksPermission;
        $("#documentContentInput").setAttribute("contenteditable", String(!locked));
        $("#documentTitleInput").readOnly = locked;
        $$(".document-toolbar button, .document-toolbar select").forEach((control) => { control.disabled = locked; });
        $("#documentProjectInput").disabled = Boolean(documentLoading || documentSaveInFlight || documentLoadFailed || editingDocument || contextualDocumentProjectId);
        $("#saveDocumentBtn").hidden = Boolean(lacksPermission || documentLoadFailed);
        $("#saveDocumentBtn").disabled = locked;
        $("#deleteDocumentBtn").hidden = !editingDocument || !editingDocument.puede_eliminar;
        $("#deleteDocumentBtn").disabled = Boolean(documentLoading || documentSaveInFlight || documentLoadFailed || !editingDocument?.puede_eliminar);
    }

    function applyDocumentToEditor(documento) {
        editingDocument = documento;
        $("#documentModalTitle").textContent = documento ? documento.titulo : "Nuevo documento";
        $("#documentTitleInput").value = documento?.titulo || "";
        renderDocumentContent(documento?.contenido || "");
        documentEditRevision = 0;
        documentSelectionRange = null;
        $("#documentProjectInput").value = documento?.proyecto_id || contextualDocumentProjectId || "";
        $("#documentVersionLabel").textContent = documento ? `Version ${documento.version}` : "";
        updateDocumentControls();
    }

    function closeDocument() {
        documentSession += 1;
        documentModal?.classList.remove("show");
        const returnProjectId = projectResourcesReturnId;
        projectResourcesReturnId = null;
        contextualDocumentProjectId = null;
        if (returnProjectId) {
            const project = projects.find((item) => item.id === returnProjectId);
            if (project) openProjectResources(project);
        }
    }

    async function openDocument(documento = null, projectId = null) {
        const session = ++documentSession;
        contextualDocumentProjectId = projectId || null;
        projectResourcesReturnId = projectId || null;
        if (projectId && $("#projectDocumentsModal")?.open) $("#projectDocumentsModal").close();
        documentConflictPending = false;
        documentConflictVersion = null;
        latestConflictDocument = null;
        documentLoadFailed = false;
        documentLoading = Boolean(documento);
        $("#documentFormError").textContent = "";
        $("#documentConflict").hidden = true;
        $("#documentRestoreVersionBtn").hidden = true;
        applyDocumentToEditor(documento ? { ...documento } : null);
        updateDocumentControls();
        documentModal.classList.add("show");
        if (!documento) return;
        try {
            const result = await api(`/documentos/api/${documento.id}/`);
            if (session !== documentSession) return;
            applyDocumentToEditor(result.documento);
        } catch (error) {
            if (session !== documentSession) return;
            documentLoadFailed = true;
            $("#documentFormError").textContent = error.message;
        } finally {
            if (session === documentSession) {
                documentLoading = false;
                updateDocumentControls();
            }
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
        const payload = { titulo: $("#documentTitleInput").value.trim(), contenido: serializeDocumentContent() };
        const savedRevision = documentEditRevision;
        const project = contextualDocumentProjectId || $("#documentProjectInput").value;
        if (!documentAtStart && project) payload.proyecto = Number(project);
        if (documentAtStart) payload.version = version;

        documentSaveInFlight = true;
        updateDocumentControls();
        try {
            await (documentAtStart
                ? api(`/documentos/api/${documentAtStart.id}/`, "PATCH", payload)
                : api("/documentos/api/", "POST", payload));
            documentConflictPending = false;
            documentConflictVersion = null;
            latestConflictDocument = null;
            await loadDocuments();
            if (session === documentSession && documentEditRevision === savedRevision && editingDocument?.id === documentAtStart?.id) closeDocument();
            else if (session === documentSession) {
                if (documentAtStart && editingDocument) editingDocument.version += 1;
                $("#documentFormError").textContent = "Se guardó la versión enviada; los cambios posteriores siguen en el editor y puedes guardarlos otra vez.";
            }
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
            if (session === documentSession) updateDocumentControls();
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

    function calculatedPriority(dueDate) {
        if (!dueDate) return { label: "Sin fecha", key: "no-date" };
        const [year, month, day] = dueDate.split("-").map(Number);
        const due = Date.UTC(year, month - 1, day);
        const todayParts = currentEduflowDate().split("-").map(Number);
        const today = Date.UTC(todayParts[0], todayParts[1] - 1, todayParts[2]);
        const days = Math.floor((due - today) / 86400000);
        if (days < 0) return { label: "Vencida", key: "vencida" };
        if (days <= 7) return { label: "Alta", key: "alta" };
        if (days <= 13) return { label: "Media", key: "media" };
        return { label: "Baja", key: "baja" };
    }

    function currentEduflowDate() {
        const timeZone = document.body.dataset.timezone || "UTC";
        const parts = new Intl.DateTimeFormat("en-US", {
            timeZone,
            calendar: "gregory",
            numberingSystem: "latn",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).formatToParts(new Date());
        const dateParts = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
        return dateParts.year + "-" + dateParts.month + "-" + dateParts.day;
    }

    let displayedEduflowDate = currentEduflowDate();
    let priorityRefreshInterval = null;

    function refreshPriorityViewsForNewDate() {
        const today = currentEduflowDate();
        if (today === displayedEduflowDate) return;
        displayedEduflowDate = today;
        renderTasks();
        renderProjects();
        if (projectTaskBoardId) {
            const project = projects.find((item) => item.id === projectTaskBoardId);
            if (project) openProjectTaskBoard(project);
        }
    }

    function startPriorityRefresh() {
        if (priorityRefreshInterval !== null) return;
        priorityRefreshInterval = window.setInterval(refreshPriorityViewsForNewDate, 60000);
    }

    function stopPriorityRefresh() {
        if (priorityRefreshInterval === null) return;
        window.clearInterval(priorityRefreshInterval);
        priorityRefreshInterval = null;
    }

    startPriorityRefresh();
    window.addEventListener("pagehide", stopPriorityRefresh);
    window.addEventListener("pageshow", () => {
        refreshPriorityViewsForNewDate();
        startPriorityRefresh();
    });

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
    const darkModeSwitch = $("#darkModeSwitch");
    function applyStudentTheme(dark) {
        document.body.classList.toggle("dark", dark);
        if (darkModeSwitch) darkModeSwitch.checked = dark;
        if (themeBtn) themeBtn.textContent = dark ? "☀️" : "🌙";
        localStorage.setItem("darkMode", String(dark));
    }
    if (darkModeSwitch) {
        applyStudentTheme(localStorage.getItem("darkMode") === "true");
        darkModeSwitch.addEventListener("change", () => applyStudentTheme(darkModeSwitch.checked));
    } else if (themeBtn) {
        themeBtn.textContent = document.body.classList.contains("dark") ? "☀️" : "🌙";
    }
    themeBtn?.addEventListener("click", () => applyStudentTheme(!document.body.classList.contains("dark")));
    $("#profileBtn")?.addEventListener("click", () => $("#profileModal")?.showModal());

    const taskModal = $("#taskModal");
    const projectModal = $("#projectModal");
    function closeTaskModal(force = false) {
        if (taskSaveInFlight && !force) return;
        taskModal?.classList.remove("show");
    }
    function closeProjectModal(force = false) {
        if (projectSaveInFlight && !force) return;
        projectModal?.classList.remove("show");
    }
    function setTaskModalBusy(busy) {
        ["#taskInput", "#taskDescription", "#taskDueDate", "#taskStateInput", "#saveTask", "#deleteTaskBtn", "#closeModal"]
            .forEach((selector) => { const control = $(selector); if (control) control.disabled = busy; });
    }
    function setProjectModalBusy(busy) {
        ["#projectNameInput", "#projectDescriptionInput", "#projectDueDateInput", "#projectMembersInput", "#saveProjectBtn", "#deleteProjectBtn"]
            .forEach((selector) => { const control = $(selector); if (control) control.disabled = busy; });
        $$('[data-close-project]').forEach((control) => { control.disabled = busy; });
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
                card.appendChild(make("strong", "", task.titulo));
                if (task.descripcion) card.appendChild(make("p", "", task.descripcion));
                const priority = calculatedPriority(task.fecha_vencimiento);
                card.appendChild(make("span", `card-date priority ${priority.key}`, `${dateLabel(task.fecha_vencimiento)} · Prioridad ${priority.label}`));
                const actions = make("div", "task-card-actions");
                const stateSelect = document.createElement("select");
                stateSelect.setAttribute("aria-label", `Estado de ${task.titulo}`);
                states.forEach(([value, text]) => {
                    const option = new Option(text, value, false, task.estado === value);
                    stateSelect.add(option);
                });
                stateSelect.addEventListener("change", async () => {
                    try { await api(`${taskUrl}${task.id}/`, "PATCH", { estado: stateSelect.value }); await loadTasks(); }
                    catch (error) { stateSelect.value = task.estado; notify(error.message, true); }
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
        const pendingTasks = allPersonalTasks.filter((task) => task.estado !== "completada");
        const pending = pendingTasks.length;
        const overdue = pendingTasks.filter((task) => calculatedPriority(task.fecha_vencimiento).key === "vencida").length;
        const upcoming = pendingTasks.filter((task) => ["alta", "media"].includes(calculatedPriority(task.fecha_vencimiento).key)).length;
        $("#taskCountText")?.replaceChildren(document.createTextNode(`${pending} tareas pendientes`));
        $("#taskSummaryText")?.replaceChildren(document.createTextNode(`${pending} pendientes · ${overdue} vencidas · ${upcoming} próximas a vencer.`));
        renderUpcomingTasks();
    }

    function renderUpcomingTasks() {
        const list = $("#upcomingTaskList");
        if (!list) return;
        list.replaceChildren();
        const upcoming = [...allPersonalTasks]
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
            const priority = calculatedPriority(task.fecha_vencimiento);
            row.appendChild(make("span", `priority ${priority.key}`, priority.label));
            list.appendChild(row);
        });
    }

    function applyTaskFilters() {
        const status = $("#filterTaskStatus")?.value;
        const from = $("#filterTaskFrom")?.value;
        const to = $("#filterTaskTo")?.value;
        const error = $("#taskFilterError");
        if (from && to && from > to) {
            if (error) error.textContent = "La fecha inicial debe ser anterior o igual a la fecha final.";
            personalTasks = [];
            renderTasks();
            return;
        }
        if (error) error.textContent = "";
        personalTasks = allPersonalTasks.filter((task) => {
            if (status && task.estado !== status) return false;
            const due = task.fecha_vencimiento || "";
            if (from && (!due || due < from)) return false;
            if (to && (!due || due > to)) return false;
            return true;
        });
        renderTasks();
    }

    async function loadTasks() {
        const requestId = ++taskListRequest;
        try {
            const result = await api(taskUrl);
            if (requestId !== taskListRequest) return;
            allPersonalTasks = result.tareas;
            applyTaskFilters();
        } catch (error) { if (requestId === taskListRequest) notify(error.message, true); }
    }

    function openTask(task = null, projectId = null) {
        if (taskSaveInFlight) return;
        editingTask = task;
        taskProjectId = projectId || task?.proyecto_id || null;
        $("#taskModalTitle").textContent = task ? "Editar tarea" : (taskProjectId ? "Nueva tarea del equipo" : "Nueva tarea");
        $("#taskInput").value = task?.titulo || "";
        $("#taskDescription").value = task?.descripcion || "";
        $("#taskDueDate").value = task?.fecha_vencimiento || "";
        $("#taskStateInput").value = task?.estado || "pendiente";
        $("#taskFormError").textContent = "";
        $("#deleteTaskBtn").hidden = !task;
        taskModal.classList.add("show");
        $("#taskInput").focus();
    }

    async function saveTask() {
        if (taskSaveInFlight) return;
        const data = {
            titulo: $("#taskInput").value.trim(),
            descripcion: $("#taskDescription").value.trim(),
            fecha_vencimiento: $("#taskDueDate").value,
            estado: $("#taskStateInput").value,
        };
        if (!data.titulo) { $("#taskFormError").textContent = "Escribe un título para la tarea."; return; }
        if (!editingTask && taskProjectId) data.proyecto = taskProjectId;
        taskSaveInFlight = true;
        setTaskModalBusy(true);
        try {
            if (editingTask) await api(`${taskUrl}${editingTask.id}/`, "PATCH", data);
            else await api(taskUrl, "POST", data);
            closeTaskModal(true);
            await Promise.all([loadTasks(), loadProjects()]);
            if (projectTaskBoardId) {
                const refreshed = projects.find((item) => item.id === projectTaskBoardId);
                if (refreshed) openProjectTaskBoard(refreshed);
            }
            notify(editingTask ? "Tarea actualizada." : "Tarea creada.");
        } catch (error) { $("#taskFormError").textContent = error.message; }
        finally { taskSaveInFlight = false; setTaskModalBusy(false); }
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
            const card = make("article", "project-card folder-project-card");
            card.appendChild(make("div", "project-icon", "📁"));
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

            card.appendChild(make("span", "project-work-type", project.integrantes.length > 1 ? "Trabajo grupal" : "Trabajo individual"));
            const actions = make("div", "project-actions");
            const addTask = make("button", "secondary-button", "Tareas");
            addTask.type = "button";
            addTask.addEventListener("click", () => openProjectTaskBoard(project));
            actions.appendChild(addTask);
            const documents = make("button", "secondary-button", "Documentos");
            documents.type = "button";
            documents.addEventListener("click", () => openProjectResources(project));
            actions.appendChild(documents);
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
                const priority = calculatedPriority(task.fecha_vencimiento);
                details.appendChild(make("small", "", `${states.find(([value]) => value === task.estado)?.[1] || task.estado} · ${priority.label} · ${dateLabel(task.fecha_vencimiento)}`));
                row.appendChild(details);

                const deliveryPanel = make("div", "group-delivery-panel");
                deliveryPanel.appendChild(make("strong", "", "Entrega grupal"));
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
            if (project.devoluciones && project.devoluciones.length) {
                const feedback = make("div", "project-feedback-history");
                feedback.appendChild(make("h4", "", "Devoluciones docentes"));
                project.devoluciones.forEach((entry) => {
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
        const requestId = ++projectListRequest;
        try {
            const nextProjects = (await api(projectUrl)).proyectos;
            await Promise.all(nextProjects.flatMap((project) => project.tareas.map(async (task) => {
                const [deliveries, evaluations] = await Promise.all([
                    api(`${taskUrl}${task.id}/entregas/`),
                    api(`${taskUrl}${task.id}/evaluaciones/`),
                ]);
                task.entregas = deliveries.entregas;
                task.evaluacion_grupal = evaluations.grupal;
                task.evaluacion_individual = evaluations.individuales[0] || null;
            })));
            if (requestId !== projectListRequest) return;
            projects = nextProjects;
            renderProjects();
        } catch (error) { if (requestId === projectListRequest) notify(error.message, true); }
    }

    async function openProjectResources(project) {
        projectResourcesId = project.id;
        $("#projectDocumentsTitle").textContent = "Documentos · " + project.nombre;
        $("#projectDocumentsMeta").textContent = "Archivos y documentos asociados a este proyecto.";
        const filesList = $("#projectResourceFiles");
        const documentsList = $("#projectResourceDocuments");
        filesList.replaceChildren(make("p", "empty-state", "Cargando archivos…"));
        documentsList.replaceChildren(make("p", "empty-state", "Cargando documentos…"));
        if (!$("#projectDocumentsModal").open) $("#projectDocumentsModal").showModal();
        const requestId = ++projectResourcesRequest;
        try {
            const query = "?proyecto=" + encodeURIComponent(project.id);
            const [fileResult, documentResult] = await Promise.all([
                api("/archivos/api/" + query),
                api("/documentos/api/" + query),
            ]);
            if (requestId !== projectResourcesRequest || projectResourcesId !== project.id) return;

            filesList.replaceChildren();
            const projectFiles = fileResult.archivos.filter((file) => Number(file.proyecto_id) === Number(project.id));
            if (!projectFiles.length) filesList.appendChild(make("p", "empty-state", "Este proyecto todavía no tiene archivos."));
            projectFiles.forEach((file) => {
                const card = make("article", "file-card");
                const extension = file.nombre.split(".").pop().toUpperCase();
                card.appendChild(make("div", "file-icon", extension));
                card.appendChild(make("strong", "", file.nombre));
                card.appendChild(make("span", "", formatBytes(file.tamano) + " · " + dateLabel(file.fecha_subida.slice(0, 10))));
                const link = make("a", "text-button", "Descargar");
                link.href = file.descarga;
                link.setAttribute("aria-label", "Descargar " + file.nombre);
                card.appendChild(link);
                filesList.appendChild(card);
            });

            documentsList.replaceChildren();
            const projectDocuments = documentResult.documentos.filter((item) => Number(item.proyecto_id) === Number(project.id));
            if (!projectDocuments.length) documentsList.appendChild(make("p", "empty-state", "Este proyecto todavía no tiene documentos."));
            projectDocuments.forEach((item) => {
                const card = make("article", "document-card");
                card.appendChild(make("strong", "", item.titulo));
                card.appendChild(make("span", "", "Guardado " + dateLabel(item.fecha_actualizacion.slice(0, 10))));
                const open = make("button", "text-button", item.puede_editar ? "Abrir y editar" : "Ver");
                open.type = "button";
                open.addEventListener("click", () => openDocument(item, project.id));
                card.appendChild(open);
                documentsList.appendChild(card);
            });
        } catch (error) {
            if (requestId !== projectResourcesRequest) return;
            filesList.replaceChildren(make("p", "form-error", "No se pudieron cargar los archivos: " + error.message));
            documentsList.replaceChildren(make("p", "form-error", "No se pudieron cargar los documentos: " + error.message));
        }
    }

    function openProjectTaskBoard(project) {
        projectTaskBoardId = project.id;
        $("#projectTaskBoardTitle").textContent = "Tareas · " + project.nombre;
        $("#projectTaskBoardMeta").textContent = "Entrega: " + dateLabel(project.fecha_entrega) + " · " + (project.integrantes.length > 1 ? "Trabajo grupal" : "Trabajo individual");
        const board = $("#projectTaskBoard");
        board.replaceChildren();
        states.forEach(([state, label]) => {
            const tasks = project.tareas.filter((task) => Number(task.proyecto_id) === Number(project.id) && task.estado === state);
            const column = make("div", "kanban-column");
            const heading = make("div", "kanban-title", label);
            heading.appendChild(make("b", "", String(tasks.length)));
            column.appendChild(heading);
            if (!tasks.length) column.appendChild(make("p", "empty-state", "No hay tareas en este estado."));
            tasks.forEach((task) => {
                const card = make("article", "kanban-card");
                card.appendChild(make("strong", "", task.titulo));
                if (task.descripcion) card.appendChild(make("p", "", task.descripcion));
                const priority = calculatedPriority(task.fecha_vencimiento);
                card.appendChild(make("span", "priority " + priority.key, priority.label + " · " + dateLabel(task.fecha_vencimiento)));
                const stateSelect = document.createElement("select");
                stateSelect.setAttribute("aria-label", "Estado de " + task.titulo);
                states.forEach(([value, text]) => stateSelect.add(new Option(text, value, false, task.estado === value)));
                stateSelect.addEventListener("change", async () => {
                    try {
                        await api(taskUrl + task.id + "/", "PATCH", { estado: stateSelect.value });
                        await loadProjects();
                        const refreshed = projects.find((item) => item.id === projectTaskBoardId);
                        if (refreshed) openProjectTaskBoard(refreshed);
                    } catch (error) { stateSelect.value = task.estado; notify(error.message, true); }
                });
                const edit = make("button", "text-button", "Editar");
                edit.type = "button";
                edit.addEventListener("click", () => {
                    returningFromProjectTaskBoard = true;
                    $("#projectTaskBoardModal").close();
                    openTask(task, project.id);
                });
                card.append(stateSelect, edit);
                column.appendChild(card);
            });
            board.appendChild(column);
        });
        if (!$("#projectTaskBoardModal").open) $("#projectTaskBoardModal").showModal();
    }

    async function openProject(project = null) {
        if (projectSaveInFlight) return;
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
        if (projectSaveInFlight) return;
        const data = {
            nombre: $("#projectNameInput").value.trim(),
            descripcion: $("#projectDescriptionInput").value.trim(),
            fecha_entrega: $("#projectDueDateInput").value,
            integrantes: [...$("#projectMembersInput").selectedOptions].map((option) => Number(option.value)),
        };
        if (!data.nombre) { $("#projectFormError").textContent = "Escribe un nombre para el proyecto."; return; }
        projectSaveInFlight = true;
        setProjectModalBusy(true);
        try {
            if (editingProject) await api(`${projectUrl}${editingProject.id}/`, "PATCH", data);
            else await api(projectUrl, "POST", data);
            closeProjectModal(true);
            await loadProjects();
            notify(editingProject ? "Proyecto actualizado." : "Proyecto creado.");
        } catch (error) { $("#projectFormError").textContent = error.message; }
        finally { projectSaveInFlight = false; setProjectModalBusy(false); }
    }

    async function deleteProject() {
        if (!editingProject || projectSaveInFlight || !window.confirm(`¿Eliminar “${editingProject.nombre}”? Solo se puede borrar si no tiene tareas, documentos ni devoluciones académicas asociadas.`)) return;
        projectSaveInFlight = true;
        setProjectModalBusy(true);
        try {
            await api(`${projectUrl}${editingProject.id}/`, "DELETE", {});
            closeProjectModal(true);
            await loadProjects();
            notify("Proyecto eliminado.");
        } catch (error) { $("#projectFormError").textContent = error.message; }
        finally { projectSaveInFlight = false; setProjectModalBusy(false); }
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
    ["#filterTaskStatus", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => {
        $(selector)?.addEventListener("change", applyTaskFilters);
    });
    $("#clearTaskFilters")?.addEventListener("click", () => {
        ["#filterTaskStatus", "#filterTaskFrom", "#filterTaskTo"].forEach((selector) => { if ($(selector)) $(selector).value = ""; });
        applyTaskFilters();
    });

    $("#closeProjectTaskBoard")?.addEventListener("click", () => $("#projectTaskBoardModal")?.close());
    $("#backFromProjectTasks")?.addEventListener("click", () => $("#projectTaskBoardModal")?.close());
    $("#projectTaskBoardModal")?.addEventListener("close", () => {
        if (returningFromProjectTaskBoard) {
            returningFromProjectTaskBoard = false;
            return;
        }
        projectTaskBoardId = null;
    });
    $("#newProjectBoardTask")?.addEventListener("click", () => {
        const project = projects.find((item) => item.id === projectTaskBoardId);
        returningFromProjectTaskBoard = true;
        $("#projectTaskBoardModal")?.close();
        if (project) openTask(null, project.id);
    });
    $("#projectDocumentsModal")?.addEventListener("close", () => {
        projectResourcesRequest += 1;
        projectResourcesId = null;
    });
    $("#closeProjectDocuments")?.addEventListener("click", () => $("#projectDocumentsModal")?.close());
    $("#backFromProjectDocuments")?.addEventListener("click", () => $("#projectDocumentsModal")?.close());
    $("#newProjectDocument")?.addEventListener("click", () => {
        if (projectResourcesId) openDocument(null, projectResourcesId);
    });
    $("#uploadProjectResource")?.addEventListener("click", () => $("#projectResourceFileInput")?.click());
    $("#projectResourceFileInput")?.addEventListener("change", async (event) => {
        const file = event.target.files?.[0];
        const projectId = projectResourcesId;
        if (!file || !projectId) return;
        const data = new FormData();
        data.append("archivo", file);
        data.append("proyecto", String(projectId));
        try {
            const response = await fetch("/archivos/api/", {
                method: "POST",
                headers: { "X-CSRFToken": csrf, Accept: "application/json" },
                body: data,
            });
            if (response.redirected) {
                window.location.assign(response.url);
                throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
            }
            let result = {};
            try { result = await response.json(); } catch (_) { /* respuesta sin JSON */ }
            if (!response.ok) throw new Error(result.error || "No se pudo subir el archivo.");
            notify("Archivo asociado al proyecto.");
            const project = projects.find((item) => item.id === projectId);
            if (projectResourcesId === projectId && project) await openProjectResources(project);
        } catch (error) {
            notify(error.message, true);
        } finally {
            event.target.value = "";
        }
    });
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
        } catch (error) { notify(error.message, true); }
        event.target.value = "";
    });
    $("#fileProjectFilter")?.addEventListener("change", () => {
        const projectSelect = $("#documentProjectInput");
        if (projectSelect) projectSelect.value = "";
        loadFiles();
    });
    $("#fileFolderFilter")?.addEventListener("change", loadFiles);
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
        } catch (error) { notify(error.message, true); }
    });
    $("#newDocumentBtn")?.addEventListener("click", () => openDocument());
    $("#saveDocumentBtn")?.addEventListener("click", saveDocument);
    $("#deleteDocumentBtn")?.addEventListener("click", deleteDocument);
    $("#documentRestoreVersionBtn")?.addEventListener("click", restoreLatestDocumentVersion);
    serializeDocumentFromEditor();
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
    loadFolders().catch((error) => notify(error.message, true));
    loadDocuments();
})();
