/**
 * Header behaviour: glass after scroll, and the mobile overlay menu.
 *
 * The glass is applied via a data attribute so the CSS owns the appearance; JS only
 * reports the scroll state. Scroll work is rAF-throttled to avoid layout thrash.
 */

import { isFinePointer } from "./reduced-motion.js";

export function initHeader() {
  const header = document.querySelector("[data-header]");
  const nav = document.querySelector("[data-nav]");
  const toggle = document.querySelector("[data-nav-toggle]");

  // --- Glass on scroll -----------------------------------------------------
  if (header) {
    let ticking = false;
    const threshold = 80;

    const update = () => {
      header.dataset.scrolled = String(window.scrollY > threshold);
      ticking = false;
    };

    window.addEventListener(
      "scroll",
      () => {
        if (!ticking) {
          window.requestAnimationFrame(update);
          ticking = true;
        }
      },
      { passive: true }
    );

    update();
  }

  // --- Mobile overlay menu -------------------------------------------------
  if (nav && toggle) {
    // Give the nav the id the toggle's aria-controls points at.
    if (!nav.id) nav.id = "primary-nav";

    const setOpen = (open) => {
      nav.dataset.open = String(open);
      toggle.setAttribute("aria-expanded", String(open));
      document.body.style.overflow = open ? "hidden" : "";
      if (open) {
        nav.querySelector("a")?.focus();
      } else {
        toggle.focus();
      }
    };

    toggle.addEventListener("click", () => {
      setOpen(nav.dataset.open !== "true");
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && nav.dataset.open === "true") {
        setOpen(false);
      }
    });

    // Never leave the menu stuck open when resizing up to desktop.
    window.addEventListener("resize", () => {
      if (isFinePointer() && nav.dataset.open === "true") setOpen(false);
    });
  }
}
