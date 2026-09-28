/**
 * TattoWeb — entry point.
 *
 * Every module is progressive enhancement: with JS disabled the site renders fully
 * resolved, forms submit, filters work and every image is reachable. Nothing here is
 * required for content to be readable.
 *
 * Budget: < 30KB total, no bundler, no dependencies.
 */

import { initHeader } from "./modules/header.js";
import { initReveal } from "./modules/reveal.js";
import { initDitherResolve } from "./modules/resolve.js";
import { initLightbox } from "./modules/lightbox.js";
import { initAccordion } from "./modules/accordion.js";
import { initBookingForm } from "./modules/booking.js";

const start = () => {
  initHeader();
  initReveal();
  initDitherResolve();
  initLightbox();
  initAccordion();
  initBookingForm();
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start, { once: true });
} else {
  start();
}
