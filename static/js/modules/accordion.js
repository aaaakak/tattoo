/**
 * Minimal accordion — the "+" affordance from the reference design.
 *
 * Native <button> with aria-expanded and a hidden panel, so screen readers announce the
 * state correctly. With JS disabled the panels stay closed and their content is simply
 * not visible; the same information is available on the page elsewhere.
 */

export function initAccordion() {
  document.querySelectorAll("[data-accordion-trigger]").forEach((trigger) => {
    const panel = trigger.nextElementSibling;
    if (!panel) return;

    trigger.addEventListener("click", () => {
      const expanded = trigger.getAttribute("aria-expanded") === "true";
      trigger.setAttribute("aria-expanded", String(!expanded));
      panel.hidden = expanded;
    });
  });
}
