"use strict";

const liveStatus = document.getElementById("live-status");
const liveLink = document.getElementById("live-link");
const liveRetry = document.getElementById("live-retry");
const readinessUrl = "https://scifact.ediacarian.dedyn.io/readyz";

function setUnavailable(message) {
  liveLink.hidden = true;
  liveStatus.dataset.state = "offline";
  liveStatus.textContent = message;
}

async function checkReadiness() {
  liveRetry.disabled = true;
  liveStatus.dataset.state = "loading";
  liveStatus.textContent = "Checking live availability…";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3500);
  try {
    const response = await fetch(readinessUrl, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      signal: controller.signal,
    });
    if (response.status === 200) {
      const payload = await response.json();
      if (
        payload &&
        payload.schema_version === "readiness/v1" &&
        payload.status === "ready"
      ) {
        liveLink.hidden = false;
        liveStatus.dataset.state = "ready";
        liveStatus.textContent = "The live demo is ready.";
        return;
      }
    }
    setUnavailable("The live demo is temporarily unavailable. The recording remains available below.");
  } catch (_error) {
    setUnavailable("The live demo is temporarily unavailable. The recording remains available below.");
  } finally {
    clearTimeout(timeout);
    liveRetry.disabled = false;
  }
}

liveRetry.addEventListener("click", () => {
  void checkReadiness();
});

void checkReadiness();
