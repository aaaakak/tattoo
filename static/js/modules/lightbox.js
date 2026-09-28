/**
 * Fullscreen image viewer.
 *
 * Progressive enhancement: the markup is always present and the trigger elements are
 * ordinary buttons wrapping the image. With JS disabled the images still render inline
 * and each card links to its detail page, so nothing becomes unreachable.
 *
 * Accessibility: focus is trapped while open and returned to the trigger on close;
 * arrow keys navigate; Escape closes.
 */

const FOCUSABLE = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export function initLightbox() {
  const boxes = document.querySelectorAll(".lightbox");
  if (!boxes.length) return;

  boxes.forEach((box) => {
    const dataEl = box.querySelector("[data-lb-items]");
    if (!dataEl) return;

    let items = [];
    try {
      items = JSON.parse(dataEl.textContent) || [];
    } catch (err) {
      console.warn("[TattoWeb] lightbox: unreadable item payload", err);
      return;
    }
    if (!items.length) return;

    const img = box.querySelector("[data-lb-image]");
    const titleEl = box.querySelector("[data-lb-title]");
    const metaEl = box.querySelector("[data-lb-meta]");
    const counter = box.querySelector("[data-lb-counter]");
    const uid = box.id;
    let index = 0;
    let lastTrigger = null;

    const pad = (n) => String(n).padStart(2, "0");

    const show = (i) => {
      index = (i + items.length) % items.length;
      const item = items[index];
      // Swap the dither plate out and load the full image; the viewer always shows the
      // artwork at full fidelity, never the halftone.
      img.src = item.url;
      img.alt = item.alt || item.title || "";
      if (titleEl) titleEl.textContent = item.title || "";
      if (metaEl) metaEl.textContent = item.meta || "";
      if (counter) counter.textContent = `${pad(index + 1)} / ${pad(items.length)}`;
    };

    const open = (i, trigger) => {
      lastTrigger = trigger || null;
      show(i);
      box.hidden = false;
      document.body.classList.add("lightbox-open");
      (box.querySelector("[data-lb-close]") || box).focus();
    };

    const close = () => {
      box.hidden = true;
      document.body.classList.remove("lightbox-open");
      img.src = "";
      if (lastTrigger) lastTrigger.focus();
    };

    const isOpen = () => !box.hidden;

    // Triggers
    document.querySelectorAll(`[data-lb-open="${uid}"]`).forEach((trigger) => {
      trigger.addEventListener("click", (event) => {
        event.preventDefault();
        open(parseInt(trigger.dataset.lbIndex || "0", 10), trigger);
      });
    });

    box.querySelector("[data-lb-close]")?.addEventListener("click", close);
    box.querySelector("[data-lb-prev]")?.addEventListener("click", () => show(index - 1));
    box.querySelector("[data-lb-next]")?.addEventListener("click", () => show(index + 1));

    // Click the backdrop (but not the image) to close.
    box.addEventListener("click", (event) => {
      if (event.target === box) close();
    });

    // Keyboard
    box.addEventListener("keydown", (event) => {
      if (event.key === "Escape") { close(); return; }
      if (event.key === "ArrowLeft") { show(index - 1); return; }
      if (event.key === "ArrowRight") { show(index + 1); return; }
      if (event.key === "Home") { show(0); return; }
      if (event.key === "End") { show(items.length - 1); return; }

      // Trap focus inside the dialog.
      if (event.key === "Tab") {
        const focusables = [...box.querySelectorAll(FOCUSABLE)].filter((el) => !el.disabled);
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    });

    // Touch: horizontal swipe
    let touchStartX = null;
    box.addEventListener("touchstart", (e) => { touchStartX = e.changedTouches[0].clientX; }, { passive: true });
    box.addEventListener("touchend", (e) => {
      if (touchStartX === null) return;
      const dx = e.changedTouches[0].clientX - touchStartX;
      if (Math.abs(dx) > 50) show(dx < 0 ? index + 1 : index - 1);
      touchStartX = null;
    }, { passive: true });

    // Preload neighbours so navigation feels instant.
    const preload = () => {
      [index - 1, index + 1].forEach((i) => {
        const item = items[(i + items.length) % items.length];
        if (item) new Image().src = item.url;
      });
    };
    box.addEventListener("transitionend", preload);
    setInterval(() => { if (isOpen()) preload(); }, 1500);
  });
}
