// Shared UI behavior: confirmation dialog and tooltips.
document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("confirmModal");
  if (modal) {
    modal.addEventListener("show.bs.modal", (event) => {
      const data = event.relatedTarget.dataset;
      modal.querySelector("form").action = data.confirmUrl;
      // textContent (not innerHTML): names typed by users can never inject HTML here.
      modal.querySelector("[data-confirm-title]").textContent = data.confirmTitle || "Confirmar";
      modal.querySelector("[data-confirm-message]").textContent = data.confirmMessage || "¿Seguro que deseas continuar?";
      const submit = modal.querySelector("[data-confirm-submit]");
      submit.textContent = data.confirmLabel || "Confirmar";
      submit.className = `btn btn-${data.confirmVariant || "danger"}`;
    });
  }

  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
});
