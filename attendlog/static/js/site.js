"use strict";

// The scanner illustration does not request a camera or mark attendance.
const dialog = document.querySelector("#access-notice");
if (dialog && typeof dialog.showModal === "function") {
  const title = dialog.querySelector("#access-title");
  const message = dialog.querySelector("#access-message");
  const notices = {
    attendance: ["Live attendance", "Live attendance is not available yet."],
  };
  let trigger = null;
  function openNotice(kind) {
    [title.textContent, message.textContent] = notices[kind];
    dialog.showModal();
  }
  document.querySelectorAll("[data-access]").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      trigger = link;
      openNotice(link.dataset.access);
    });
  });
  if (dialog.dataset.initialAccess) {
    const kind = dialog.dataset.initialAccess;
    dialog.close();
    openNotice(kind);
  }
  dialog.addEventListener("close", () => {
    trigger?.focus();
    if (dialog.dataset.initialAccess) {
      window.history.replaceState(null, "", "/");
      delete dialog.dataset.initialAccess;
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const box = dialog.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
  });
}
