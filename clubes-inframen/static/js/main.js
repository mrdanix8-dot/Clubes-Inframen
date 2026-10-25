// Theme toggle + small UX helpers

document.addEventListener("DOMContentLoaded", () => {
    // ---- Modo claro / oscuro ----
    const toggle = document.getElementById("theme-toggle");
    const html = document.documentElement;

    // Cargar preferencia guardada
    const saved = localStorage.getItem("inframen-theme") || "dark";
    html.setAttribute("data-theme", saved);
    updateIcon(saved);

    if (toggle) {
        toggle.addEventListener("click", () => {
            const current = html.getAttribute("data-theme");
            const next = current === "dark" ? "light" : "dark";
            html.setAttribute("data-theme", next);
            localStorage.setItem("inframen-theme", next);
            updateIcon(next);
        });
    }

    function updateIcon(theme) {
        if (!toggle) return;
        toggle.innerHTML = theme === "dark" ? "☀️" : "🌙";
        toggle.title = theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro";
    }

    // ---- Tabs de login (Estudiante / Docente) ----
    const roleBtns = document.querySelectorAll(".role-tabs button");
    const rolInput = document.getElementById("rol-input");
    const extraFields = document.getElementById("extra-docente");

    roleBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            roleBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            if (rolInput) rolInput.value = btn.dataset.rol;

            if (extraFields) {
                extraFields.style.display = btn.dataset.rol === "docente" ? "block" : "none";
            }
        });
    });

    // ---- Toggle registro / login ----
    const showReg = document.getElementById("show-registro");
    const showLog = document.getElementById("show-login");
    const formLogin = document.getElementById("form-login");
    const formReg = document.getElementById("form-registro");

    if (showReg) {
        showReg.addEventListener("click", e => {
            e.preventDefault();
            formLogin.style.display = "none";
            formReg.style.display = "block";
        });
    }
    if (showLog) {
        showLog.addEventListener("click", e => {
            e.preventDefault();
            formReg.style.display = "none";
            formLogin.style.display = "block";
        });
    }

    // ---- Filtros de catálogo ----
    const filterBtns = document.querySelectorAll(".filter-btn");
    const clubCards = document.querySelectorAll("[data-categoria]");

    filterBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            filterBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const cat = btn.dataset.filter;

            clubCards.forEach(card => {
                if (cat === "todos" || card.dataset.categoria === cat) {
                    card.style.display = "";
                } else {
                    card.style.display = "none";
                }
            });
        });
    });

    // ---- Auto-ocultar alertas ----
    setTimeout(() => {
        document.querySelectorAll(".alert").forEach(a => {
            a.style.opacity = "0";
            a.style.transform = "translateX(40px)";
            setTimeout(() => a.remove(), 400);
        });
    }, 4500);
});
