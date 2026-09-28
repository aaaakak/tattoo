/**
 * Dither -> full image resolution.
 *
 * The signature interaction. The dither variant is pre-generated at upload, so this
 * module does NO image processing: it only swaps which pre-built layer is visible.
 *
 * Strategy:
 *  - If the dither derivative exists (data-dither-src), mark the figure ready so CSS
 *    shows the dither rest state.
 *  - Resolution on hover/focus is pure CSS. This module handles only the
 *    scroll-triggered cases (hero, `data-resolve-on="view"`).
 *
 * If the derivative is missing, the component already degrades to the full image.
 */

import { prefersReducedMotion } from "./reduced-motion.js";

const probeImage = (src) =>
  new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(true);
    img.onerror = () => resolve(false);
    img.src = src;
  });

export function initDitherResolve() {
  const figures = document.querySelectorAll(".dither[data-dither-src]");
  if (!figures.length) return;

  figures.forEach(async (figure) => {
    const src = figure.dataset.ditherSrc;
    const exists = await probeImage(src);

    if (!exists) {
      // Missing derivative: degrade to the full image rather than show a broken layer.
      figure.dataset.ditherMissing = "true";
      figure.dataset.ditherReady = "false";
      console.warn("[TattoWeb] dither derivative missing, degraded to full image:", src);
      return;
    }

    figure.dataset.ditherReady = "true";
  });

  // Scroll-triggered resolution (hero and explicitly opted-in figures).
  const viewResolved = document.querySelectorAll('.dither[data-resolve-on="view"]');
  if (!viewResolved.length) return;

  if (prefersReducedMotion()) {
    viewResolved.forEach((el) => {
      el.dataset.resolved = "true";
    });
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.dataset.resolved = "true";
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.35 }
  );

  viewResolved.forEach((el) => observer.observe(el));
}
