"use strict";

const configNode = document.getElementById("scifact-config");
const form = document.getElementById("claim-form");
const queryInput = document.getElementById("claim-input");
const strategySelect = document.getElementById("strategy-select");
const contextSelect = document.getElementById("context-strategy-select");
const limitInput = document.getElementById("result-limit");
const searchButton = document.getElementById("search-button");
const answerButton = document.getElementById("answer-button");
const requestStatus = document.getElementById("request-status");
const capabilityStatus = document.getElementById("capability-status");
const showcaseLink = document.getElementById("showcase-link");
const resultSummary = document.getElementById("result-summary");
const resultKicker = document.getElementById("result-kicker");
const resultTitle = document.getElementById("result-title");
const answerText = document.getElementById("answer-text");
const resultMeta = document.getElementById("result-meta");
const citationList = document.getElementById("citation-list");
const evidenceList = document.getElementById("evidence-list");
const evidenceCount = document.getElementById("evidence-count");

const messages = {
  validation: "Request validation failed. Check the claim and controls, then try again.",
  busy: "Another live request is running. Try again shortly.",
  rateLimited: "The anonymous request allowance is exhausted. Try again later.",
  unavailable: "A required service is temporarily unavailable.",
  offline: "The live demo is offline. View the recorded showcase instead.",
  contract: "The response did not match the expected contract.",
};

let capabilitySnapshot = null;

function parseConfiguration() {
  try {
    const value = JSON.parse(configNode.textContent);
    if (
      !Array.isArray(value.retrieval_strategies) ||
      !Array.isArray(value.context_strategies) ||
      typeof value.default_retrieval_strategy !== "string" ||
      typeof value.default_context_strategy !== "string" ||
      typeof value.public_demo_enabled !== "boolean"
    ) {
      throw new Error("invalid configuration");
    }
    return value;
  } catch (_error) {
    setFailure(messages.contract);
    form.querySelectorAll("button, input, select, textarea").forEach((control) => {
      control.disabled = true;
    });
    return null;
  }
}

function addOptions(select, values, selectedValue) {
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    option.selected = value === selectedValue;
    select.append(option);
  });
}

function validCapabilityGroup(group, names) {
  return (
    group !== null &&
    typeof group === "object" &&
    typeof group.configured_default === "string" &&
    (typeof group.effective_default === "string" || group.effective_default === null) &&
    Array.isArray(group.strategies) &&
    group.strategies.length === names.length &&
    group.strategies.every(
      (item, index) =>
        item !== null &&
        typeof item === "object" &&
        item.name === names[index] &&
        typeof item.available === "boolean" &&
        (typeof item.reason === "string" || item.reason === null),
    )
  );
}

function applyCapabilityGroup(select, group) {
  markUnavailableOptions(select, group);
  if (typeof group.effective_default === "string") {
    select.value = group.effective_default;
  }
}

function markUnavailableOptions(select, group) {
  const availableByName = new Map(
    group.strategies.map((item) => [item.name, item.available]),
  );
  select.querySelectorAll("option").forEach((option) => {
    const available = availableByName.get(option.value) === true;
    option.disabled = !available;
    option.title = available ? "" : "Unavailable for the current live services.";
  });
}

function restoreCapabilityAvailability() {
  if (capabilitySnapshot === null) {
    return;
  }
  markUnavailableOptions(strategySelect, capabilitySnapshot.retrieval);
  markUnavailableOptions(contextSelect, capabilitySnapshot.context);
  answerButton.disabled = !capabilitySnapshot.answer.available;
  searchButton.disabled = !capabilitySnapshot.search.available;
}

function applyCapabilities(payload, configuration) {
  if (
    payload === null ||
    typeof payload !== "object" ||
    payload.schema_version !== "capabilities/v1" ||
    !["ready", "degraded", "unavailable"].includes(payload.status) ||
    payload.search === null ||
    typeof payload.search !== "object" ||
    typeof payload.search.available !== "boolean" ||
    payload.answer === null ||
    typeof payload.answer !== "object" ||
    typeof payload.answer.available !== "boolean" ||
    !validCapabilityGroup(payload.retrieval, configuration.retrieval_strategies) ||
    !validCapabilityGroup(payload.context, configuration.context_strategies)
  ) {
    throw new Error("contract");
  }
  capabilitySnapshot = payload;
  applyCapabilityGroup(strategySelect, payload.retrieval);
  applyCapabilityGroup(contextSelect, payload.context);
  const unavailable = payload.status === "unavailable";
  setCapabilityStatus(
    unavailable
      ? "Live capabilities are unavailable."
      : payload.status === "degraded"
        ? "Live demo is available with a fallback strategy."
        : "Live capabilities are ready.",
    unavailable ? "error" : "ready",
  );
  if (!payload.answer.available) {
    answerButton.disabled = true;
  }
  if (!payload.search.available) {
    searchButton.disabled = true;
  }
}

async function loadCapabilities(configuration) {
  if (!configuration.public_demo_enabled) {
    capabilityStatus.hidden = true;
    return;
  }
  setShowcaseLink(true);
  try {
    const response = await fetch("/v1/capabilities", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new Error("unavailable");
    }
    const payload = await response.json();
    applyCapabilities(payload, configuration);
  } catch (error) {
    setCapabilityStatus(
      error instanceof Error && error.message === "contract"
        ? messages.contract
        : messages.unavailable,
      "error",
    );
  }
}

function setBusy(busy, operation = "") {
  form.querySelectorAll("button, input, select").forEach((control) => {
    control.disabled = busy;
  });
  if (!busy) {
    restoreCapabilityAvailability();
  }
  requestStatus.dataset.state = busy ? "loading" : "ready";
  requestStatus.textContent = busy ? `${operation} in progress…` : "Request complete.";
}

function setShowcaseLink(visible) {
  if (!visible) {
    showcaseLink.hidden = true;
    return;
  }
  showcaseLink.href = "https://stauntonjr.github.io/scifact-rag/showcase/scifact-ui/";
  showcaseLink.target = "_blank";
  showcaseLink.rel = "noreferrer";
  showcaseLink.hidden = false;
}

function setCapabilityStatus(message, state = "ready") {
  capabilityStatus.dataset.state = state;
  capabilityStatus.textContent = message;
}

function clearResult() {
  resultSummary.hidden = true;
  resultSummary.dataset.state = "";
  resultKicker.textContent = "";
  resultTitle.textContent = "Result";
  answerText.textContent = "";
  resultMeta.replaceChildren();
  citationList.replaceChildren();
  evidenceList.replaceChildren();
  evidenceCount.textContent = "No evidence loaded";
}

function setFailure(message) {
  clearResult();
  requestStatus.dataset.state = "error";
  requestStatus.textContent = message;
  resultSummary.hidden = false;
  resultSummary.dataset.state = "error";
  resultKicker.textContent = "Request not completed";
  resultTitle.textContent = "Unable to show a result";
  answerText.textContent = message;
}

function appendMetadata(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  wrapper.append(term, description);
  resultMeta.append(wrapper);
}

function evidenceAnchorId(docId) {
  return `evidence-${encodeURIComponent(docId)}`;
}

function validHit(hit) {
  return (
    hit !== null &&
    typeof hit === "object" &&
    typeof hit.doc_id === "string" &&
    typeof hit.title === "string" &&
    typeof hit.text === "string" &&
    typeof hit.score === "number" &&
    Number.isFinite(hit.score)
  );
}

function groupEvidenceByParent(evidence) {
  const groups = new Map();
  evidence.forEach((hit) => {
    if (!groups.has(hit.doc_id)) {
      groups.set(hit.doc_id, {
        docId: hit.doc_id,
        title: hit.title,
        passages: [],
      });
    }
    groups.get(hit.doc_id).passages.push(hit);
  });
  return Array.from(groups.values());
}

function appendEvidencePassage(card, hit, index, passageCount) {
  const passage = document.createElement(passageCount === 1 ? "div" : "section");
  passage.className = "evidence-passage";
  if (passageCount > 1) {
    const heading = document.createElement("h4");
    heading.textContent = `Supplied passage ${index + 1}`;
    passage.append(heading);
  }

  const score = document.createElement("p");
  score.className = "score";
  score.textContent = `Score ${hit.score.toFixed(6)}`;
  const text = document.createElement("p");
  text.className = "evidence-text";
  text.textContent = hit.text;
  passage.append(score, text);
  card.append(passage);
}

function renderEvidence(evidence) {
  evidenceList.replaceChildren();
  const groups = groupEvidenceByParent(evidence);
  groups.forEach((group, index) => {
    const card = document.createElement("article");
    card.className = "evidence-card";
    card.id = evidenceAnchorId(group.docId);

    const heading = document.createElement("div");
    heading.className = "evidence-heading";
    const title = document.createElement("h3");
    title.textContent = `${index + 1}. ${group.title || "Untitled document"}`;
    const identity = document.createElement("span");
    identity.className = "document-id";
    identity.textContent = `Document ${group.docId}`;
    heading.append(title, identity);
    card.append(heading);

    if (group.passages.length > 1) {
      const contextCount = document.createElement("p");
      contextCount.className = "context-count";
      contextCount.textContent = `${group.passages.length} supplied passages`;
      card.append(contextCount);
    }
    group.passages.forEach((hit, passageIndex) => {
      appendEvidencePassage(card, hit, passageIndex, group.passages.length);
    });
    evidenceList.append(card);
  });

  const documentLabel = groups.length === 1 ? "1 document" : `${groups.length} documents`;
  evidenceCount.textContent =
    groups.length === evidence.length
      ? documentLabel
      : `${documentLabel} · ${evidence.length} supplied passages`;
}

function renderSearch(payload, strategy) {
  if (
    payload === null ||
    typeof payload !== "object" ||
    payload.schema_version !== "search-response/v1" ||
    !Array.isArray(payload.hits) ||
    !payload.hits.every(validHit)
  ) {
    throw new Error("contract");
  }
  resultSummary.hidden = false;
  resultKicker.textContent = "Document search";
  resultTitle.textContent = `${payload.hits.length} ranked result${payload.hits.length === 1 ? "" : "s"}`;
  answerText.textContent = "Inspect the complete parent-document evidence below.";
  appendMetadata("Retrieval", strategy);
  renderEvidence(payload.hits);
}

function renderAnswer(payload, strategy, contextStrategy) {
  if (
    payload === null ||
    typeof payload !== "object" ||
    payload.schema_version !== "answer/v1" ||
    typeof payload.query !== "string" ||
    typeof payload.text !== "string" ||
    typeof payload.model !== "string" ||
    !Array.isArray(payload.citations) ||
    !payload.citations.every((citation) => typeof citation === "string") ||
    !Array.isArray(payload.evidence) ||
    !payload.evidence.every(validHit)
  ) {
    throw new Error("contract");
  }

  const evidenceIds = new Set(payload.evidence.map((hit) => hit.doc_id));
  if (!payload.citations.every((citation) => evidenceIds.has(citation))) {
    throw new Error("contract");
  }

  const isInsufficient = payload.text === "insufficient evidence";
  if (
    (isInsufficient && payload.citations.length !== 0) ||
    (!isInsufficient && payload.citations.length === 0)
  ) {
    throw new Error("contract");
  }

  resultSummary.hidden = false;
  resultSummary.dataset.state = isInsufficient ? "insufficient" : "answer";
  resultKicker.textContent = isInsufficient ? "Evidence boundary reached" : "Grounded answer";
  resultTitle.textContent = isInsufficient ? "Insufficient evidence" : "Answer";
  answerText.textContent = payload.text;
  appendMetadata("Model", payload.model);
  appendMetadata("Retrieval", strategy);
  appendMetadata("Context", contextStrategy);

  payload.citations.forEach((citation) => {
    const link = document.createElement("a");
    link.className = "citation";
    link.href = `#${evidenceAnchorId(citation)}`;
    link.textContent = `Document ${citation}`;
    citationList.append(link);
  });
  renderEvidence(payload.evidence);
}

async function readJsonResponse(response) {
  if (response.status === 422) {
    throw new Error("validation");
  }
  if (response.status === 429) {
    try {
      const payload = await response.json();
      if (payload && payload.error && payload.error.code === "busy") {
        throw new Error("busy");
      }
    } catch (error) {
      if (error instanceof Error && error.message === "busy") {
        throw error;
      }
    }
    throw new Error("rate_limited");
  }
  if (response.status === 503) {
    throw new Error("unavailable");
  }
  if (response.status === 502 || response.status === 504) {
    throw new Error("offline");
  }
  if (!response.ok) {
    throw new Error("unavailable");
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error("unavailable");
  }
  return response.json();
}

async function submitRequest(operation) {
  limitInput.max = operation === "search" ? "100" : "20";
  if (!form.reportValidity()) {
    return;
  }

  clearResult();
  setBusy(true, operation === "search" ? "Search" : "Answer");
  const strategy = strategySelect.value;
  const contextStrategy = contextSelect.value;
  const body = {
    schema_version: operation === "search" ? "search-request/v1" : "ask-request/v1",
    query: queryInput.value,
    limit: Number(limitInput.value),
    strategy,
  };
  if (operation === "answer") {
    body.context_strategy = contextStrategy;
  }

  try {
    const endpoint = operation === "search" ? "/v1/search" : "/v1/ask";
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await readJsonResponse(response);
    if (operation === "search") {
      renderSearch(payload, strategy);
    } else {
      renderAnswer(payload, strategy, contextStrategy);
    }
    setBusy(false);
  } catch (error) {
    setBusy(false);
    if (error instanceof Error && error.message === "validation") {
      setFailure(messages.validation);
    } else if (error instanceof Error && error.message === "busy") {
      setFailure(messages.busy);
    } else if (error instanceof Error && error.message === "rate_limited") {
      setFailure(messages.rateLimited);
    } else if (error instanceof Error && error.message === "offline") {
      setShowcaseLink(true);
      setFailure(messages.offline);
    } else if (error instanceof Error && error.message === "contract") {
      setFailure(messages.contract);
    } else {
      setShowcaseLink(true);
      setFailure(messages.unavailable);
    }
  }
}

const configuration = parseConfiguration();
if (configuration !== null) {
  addOptions(
    strategySelect,
    configuration.retrieval_strategies,
    configuration.default_retrieval_strategy,
  );
  addOptions(
    contextSelect,
    configuration.context_strategies,
    configuration.default_context_strategy,
  );
  void loadCapabilities(configuration);
}

searchButton.addEventListener("click", () => {
  limitInput.max = "100";
});
answerButton.addEventListener("click", () => {
  limitInput.max = "20";
});
form.addEventListener("submit", (event) => {
  event.preventDefault();
  const operation = event.submitter?.value === "search" ? "search" : "answer";
  void submitRequest(operation);
});
