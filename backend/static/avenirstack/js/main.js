/* ==========================================================================
   AvenirStack · Comportamiento
   Los datos editables (correo, redes, equipo, enlaces) están en js/config.js
   ========================================================================== */
(() => {
  'use strict';

  const CFG = window.AVENIRSTACK_CONFIG || {};
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const SVG_NS = 'http://www.w3.org/2000/svg';

  /* ---------- Utilidades de DOM (siempre textContent, nunca innerHTML) ---------- */
  const el = (tag, props = {}, ...kids) => {
    const node = document.createElement(tag);
    for (const [key, val] of Object.entries(props)) {
      if (val == null || val === false) continue;
      if (key === 'class') node.className = val;
      else if (key === 'text') node.textContent = val;
      else node.setAttribute(key, val);
    }
    kids.flat().forEach((k) => k != null && node.append(k));
    return node;
  };

  const icon = (id, cls = 'i') => {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', cls);
    svg.setAttribute('aria-hidden', 'true');
    const use = document.createElementNS(SVG_NS, 'use');
    use.setAttribute('href', `#${id}`);
    svg.append(use);
    return svg;
  };

  const isFilled = (v) => typeof v === 'string' && v.trim() !== '';

  /* ---------- Cabecera: sombra al hacer scroll + volver arriba ---------- */
  function initScrollUI() {
    const header = $('#site-header');
    const toTop = $('#to-top');
    let ticking = false;

    const update = () => {
      const y = window.scrollY;
      header.classList.toggle('is-scrolled', y > 8);
      toTop.classList.toggle('is-visible', y > 640);
      ticking = false;
    };
    window.addEventListener('scroll', () => {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();

    toTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: motionQuery.matches ? 'auto' : 'smooth' });
      const home = $('#inicio');
      if (home) home.focus({ preventScroll: true });
    });
  }

  /* ---------- Menú responsive ---------- */
  function initNav() {
    const toggle = $('#nav-toggle');
    const nav = $('#site-nav');
    const mobile = window.matchMedia('(max-width: 900px)');

    const setOpen = (open) => {
      nav.classList.toggle('is-open', open);
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    };

    // En móvil el menú cerrado no debe ser alcanzable con el teclado.
    const syncInert = () => {
      const hidden = mobile.matches && !nav.classList.contains('is-open');
      if (hidden) nav.setAttribute('inert', ''); else nav.removeAttribute('inert');
    };
    const apply = (open) => { setOpen(open); syncInert(); };

    toggle.addEventListener('click', () => apply(!nav.classList.contains('is-open')));
    $$('a', nav).forEach((a) => a.addEventListener('click', () => apply(false)));
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) { apply(false); toggle.focus(); }
    });
    document.addEventListener('click', (e) => {
      if (nav.classList.contains('is-open') && !nav.contains(e.target) && !toggle.contains(e.target)) apply(false);
    });
    mobile.addEventListener('change', () => apply(false));
    apply(false);

    // Enlace activo según la sección visible
    const links = $$('.nav-list a');
    const map = new Map(links.map((a) => [a.getAttribute('href').slice(1), a]));
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((a) => a.removeAttribute('aria-current'));
          const link = map.get(entry.target.id);
          if (link) link.setAttribute('aria-current', 'location');
        });
      }, { rootMargin: '-40% 0px -55% 0px' });
      map.forEach((_, id) => { const s = document.getElementById(id); if (s) io.observe(s); });
    }
  }

  /* ---------- Animaciones de entrada ---------- */
  function initReveal() {
    const items = $$('[data-reveal]');
    if (motionQuery.matches || !('IntersectionObserver' in window)) return;
    document.documentElement.classList.add('reveal-ready');
    const io = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add('is-visible'); obs.unobserve(entry.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    items.forEach((n) => io.observe(n));
  }

  /* ---------- EduFlow: botón con destino configurable ---------- */
  function initEduflow() {
    const link = $('#eduflow-link');
    const note = $('#eduflow-note');
    if (!link) return;
    const url = (CFG.eduflow && CFG.eduflow.url) || '';
    if (isFilled(url)) {
      link.href = url.trim();
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      return;
    }
    link.addEventListener('click', (e) => {
      e.preventDefault();
      note.textContent = 'Todavía no hay un enlace configurado para EduFlow.';
      console.info('AvenirStack: completá eduflow.url en js/config.js para activar el botón «Conocer EduFlow».');
    });
  }

  /* ---------- Equipo (desde config.js) ---------- */
  function renderTeam() {
    const grid = $('#team-grid');
    if (!grid) return;
    const team = Array.isArray(CFG.team) ? CFG.team : [];
    team.forEach((m, idx) => {
      const photo = el('div', { class: 'photo' });
      if (isFilled(m.photo)) {
        photo.append(el('img', { src: m.photo.trim(), alt: `Foto de ${m.name}`, loading: 'lazy', width: 640, height: 512 }));
      } else {
        photo.append(
          el('span', { class: 'initial', 'aria-hidden': 'true', text: (m.name || '?').charAt(0).toUpperCase() }),
          el('span', { class: 'tag', text: 'Espacio para fotografía' })
        );
      }

      const skills = Array.isArray(m.skills) ? m.skills : [];
      const body = el('div', { class: 'member-body' },
        el('h3', { text: m.name }),
        isFilled(m.area) ? el('p', { class: 'area', text: m.area }) : null,
        isFilled(m.role) ? el('p', { class: 'muted', text: m.role }) : null,
        isFilled(m.description) ? el('p', { class: 'muted', text: m.description }) : null,
        skills.length ? el('p', { class: 'skills-label', text: 'Conocimientos' }) : null,
        skills.length ? el('ul', { class: 'skills', 'aria-label': `Conocimientos de ${m.name}` }, skills.map((s) => el('li', { text: s }))) : null
      );

      const card = el('article', { class: 'card card--accent member', 'data-reveal': '', style: `--d:${(idx * 0.08).toFixed(2)}s` }, photo, body);
      grid.append(card);
    });
  }

  /* ---------- Datos de contacto (desde config.js) ---------- */
  function renderContactInfo() {
    const list = $('#contact-info');
    if (!list) return;
    const contact = CFG.contact || {};

    const item = (iconId, label, content) =>
      el('li', { class: 'info-item' },
        el('span', { class: 'ico' }, icon(iconId)),
        el('div', {}, el('small', { text: label }), content)
      );

    const email = isFilled(contact.email)
      ? el('a', { href: `mailto:${contact.email.trim()}`, text: contact.email.trim() })
      : el('span', { class: 'pending', text: 'Correo por configurar' });
    list.append(item('i-mail', 'Correo electrónico', email));

    const social = Array.isArray(CFG.social) ? CFG.social : [];
    if (social.length) {
      const ul = el('ul', {}, social.map((s) => el('li', {},
        isFilled(s.url)
          ? el('a', { href: s.url.trim(), target: '_blank', rel: 'noopener noreferrer', text: s.label })
          : el('span', { class: 'pending', text: `${s.label}: por configurar` })
      )));
      list.append(item('i-link', 'Redes', ul));
    }
  }

  /* ---------- Formulario de contacto ---------- */
  function initForm() {
    const form = $('#contact-form');
    if (!form) return;
    const btn = $('#submit-btn');
    const label = $('.btn-label', btn);
    const status = $('#form-status');

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    const fields = {
      name: {
        input: $('#f-name'), error: $('#err-name'),
        check: (v) => !v ? 'Ingresá tu nombre completo.' : v.length < 3 ? 'El nombre debe tener al menos 3 caracteres.' : ''
      },
      email: {
        input: $('#f-email'), error: $('#err-email'),
        check: (v) => !v ? 'Ingresá tu correo electrónico.' : !EMAIL_RE.test(v) ? 'Ingresá un correo válido, por ejemplo nombre@dominio.com.' : ''
      },
      subject: {
        input: $('#f-subject'), error: $('#err-subject'),
        check: (v) => !v ? 'Ingresá un asunto.' : v.length < 3 ? 'El asunto debe tener al menos 3 caracteres.' : ''
      },
      message: {
        input: $('#f-message'), error: $('#err-message'),
        check: (v) => !v ? 'Escribí tu mensaje.' : v.length < 10 ? 'El mensaje debe tener al menos 10 caracteres.' : ''
      }
    };

    const showError = (f, msg) => {
      f.input.setAttribute('aria-invalid', msg ? 'true' : 'false');
      $('span', f.error).textContent = msg;
      f.error.classList.toggle('is-visible', Boolean(msg));
    };
    const validate = (f) => { const msg = f.check(f.input.value.trim()); showError(f, msg); return !msg; };

    const setStatus = (type, text) => {
      status.className = 'status';
      status.replaceChildren();
      if (!type) return;
      status.classList.add('is-visible', `status--${type}`);
      status.append(icon(type === 'success' ? 'i-check' : 'i-alert'), el('span', { text }));
    };

    const setLoading = (on) => {
      btn.disabled = on;
      btn.classList.toggle('is-loading', on);
      btn.setAttribute('aria-busy', String(on));
      label.textContent = on ? 'Enviando…' : 'Enviar mensaje';
    };

    // Validación en vivo una vez que el campo fue tocado
    Object.values(fields).forEach((f) => {
      f.input.addEventListener('blur', () => { if (f.input.value !== '' || f.input.dataset.touched) { f.input.dataset.touched = '1'; validate(f); } });
      f.input.addEventListener('input', () => { if (f.input.dataset.touched || f.input.getAttribute('aria-invalid') === 'true') validate(f); });
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      setStatus(null);

      const results = Object.values(fields).map((f) => { f.input.dataset.touched = '1'; return [f, validate(f)]; });
      const firstBad = results.find(([, ok]) => !ok);
      if (firstBad) {
        setStatus('error', 'Revisá los campos marcados y volvé a intentar.');
        firstBad[0].input.focus();
        return;
      }

      // Campo trampa para bots: si tiene contenido, se ignora el envío sin avisar.
      if ($('#f-web').value) return;

      const contact = CFG.contact || {};
      const endpoint = isFilled(contact.formEndpoint) ? contact.formEndpoint.trim() : '';
      if (!endpoint) {
        setStatus('warn', 'Tus datos son válidos, pero este formulario todavía no está conectado a un servicio de envío. Tu mensaje no fue enviado.');
        return;
      }

      const payload = {
        name: fields.name.input.value.trim(),
        email: fields.email.input.value.trim(),
        subject: fields.subject.input.value.trim(),
        message: fields.message.input.value.trim()
      };

      setLoading(true);
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 15000);
      try {
        const res = await fetch(endpoint, {
          method: contact.formMethod || 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
          signal: ctrl.signal
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setStatus('success', '¡Gracias! Recibimos tu mensaje.');
        form.reset();
        Object.values(fields).forEach((f) => { delete f.input.dataset.touched; showError(f, ''); });
      } catch (err) {
        console.error('AvenirStack: error al enviar el formulario', err);
        setStatus('error', 'No pudimos enviar tu mensaje. Revisá tu conexión e intentá de nuevo en unos minutos.');
      } finally {
        clearTimeout(timer);
        setLoading(false);
      }
    });
  }

  /* ---------- Pie de página ---------- */
  function initFooter() {
    const year = $('#year');
    if (year) year.textContent = String(new Date().getFullYear());
    const note = $('#footer-note');
    if (note) note.textContent = isFilled(CFG.footerNote) ? CFG.footerNote.trim() : '';
  }

  /* ---------- Arranque ---------- */
  function init() {
    renderTeam();
    renderContactInfo();
    initFooter();
    initNav();
    initScrollUI();
    initEduflow();
    initForm();
    initReveal();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
