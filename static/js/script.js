document.addEventListener("DOMContentLoaded", function () {
    // Mobile navigation toggle
    var toggle = document.querySelector("[data-nav-toggle]");
    var nav = document.querySelector("[data-nav]");
    if (toggle && nav) {
        toggle.addEventListener("click", function () {
            nav.classList.toggle("open");
        });
    }

    // Dismiss flash messages
    document.querySelectorAll("[data-dismiss]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            btn.closest(".alert").remove();
        });
    });

    // Auto-hide success/info alerts after 5 seconds
    document.querySelectorAll(".alert-success, .alert-info").forEach(function (alert) {
        setTimeout(function () { alert.remove(); }, 5000);
    });

    // Confirm before destructive form submissions (e.g. delete)
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            if (!confirm(form.dataset.confirm)) e.preventDefault();
        });
    });

    // Confirm before submitting feedback
    document.querySelectorAll("[data-confirm-submit]").forEach(function (btn) {
        btn.addEventListener("click", function (e) {
            var form = btn.closest("form");
            if (form.checkValidity() && !confirm(btn.dataset.confirmSubmit)) e.preventDefault();
        });
    });
});
