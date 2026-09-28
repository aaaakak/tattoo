/**
 * Scroll reveal for display typography.
 *
 * IntersectionObserver only, fired once per element, then unobserved. Both the
 * observer and the listeners detach when done, so nothing accumulates.
 */

import { prefersReducedMotion } from "./reduced-motion.js";

export function initReveal() {
  const targets = document.querySelectorAll("[data-reveal]");
  if (!targets.length) return;

  // Reduced motion: reveal immediately, no observers created at all.
  if (prefersReducedMotion()) {
    targets.forEach((el) => {
      el.dataset.revealed = "true";
    });
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.dataset.revealed = "true";
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -10% 0px" }
  );

  targets.forEach((el) => observer.observe(el));
}
