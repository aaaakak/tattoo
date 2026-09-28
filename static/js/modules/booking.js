/**
 * Booking form enhancement.
 *
 * Loads availability and constrains the date input to days that actually have open
 * slots. Entirely optional: without JS the plain date input still submits and the server
 * validates the choice in create_booking_from_payload.
 */

export function initBookingForm() {
  const dateInput = document.querySelector('input[type="date"][name="preferred_date"]');
  const status = document.querySelector("[data-availability-status]");
  if (!dateInput || !status) return;

  // The endpoint is declared by the template on an anchor element, so the date input
  // keeps whatever attributes Django's widget rendered.
  const anchor = document.querySelector("[data-availability-anchor]");
  const endpoint = anchor ? anchor.dataset.availabilityUrl : null;
  if (!endpoint) return;

  const fmt = (d) => d.toISOString().slice(0, 10);

  const load = async () => {
    const today = new Date();
    try {
      const url = new URL(endpoint, window.location.origin);
      url.searchParams.set("year", today.getFullYear());
      url.searchParams.set("month", today.getMonth() + 1);
      const res = await fetch(url, { headers: { Accept: "application/json" } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (!data.open_days || !data.open_days.length) {
        status.textContent = "// NO OPENINGS THIS MONTH — leave the date open and the studio will suggest times";
        return;
      }

      const days = new Set(data.open_days);
      const next = data.open_days[0];
      dateInput.min = fmt(today);
      status.textContent = `// ${data.count} OPEN DAY${data.count === 1 ? "" : "S"} THIS MONTH — NEXT: ${next}`;

      // Warn (do not block) when the chosen date has no availability; the server is the
      // authority and will reject it with a clear message.
      dateInput.addEventListener("change", () => {
        if (dateInput.value && !days.has(dateInput.value)) {
          status.textContent = `// ${dateInput.value} HAS NO OPENINGS — leave it open and the studio will suggest times`;
        }
      });
    } catch (err) {
      // Silent by design: availability is an enhancement, and a failure here must not
      // stop the client from submitting their request.
      console.warn("[TattoWeb] availability unavailable", err);
    }
  };

  load();
}
