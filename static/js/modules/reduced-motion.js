/**
 * Single source of truth for motion preference.
 *
 * Every module imports this rather than duplicating the media query, so
 * `prefers-reduced-motion` is honoured consistently — and can be checked cheaply.
 */

export const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const isFinePointer = () =>
  window.matchMedia("(pointer: fine)").matches;

/** Observe motion preference changes (a user can toggle it mid-session). */
export const onMotionPreferenceChange = (callback) => {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", (e) => callback(e.matches));
};
