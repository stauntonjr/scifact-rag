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
  unavailable: "The service is temporarily unavailable. Try again after it has recovered.",
  contract: "The response did not match the expected contract.",
};

function parseConfiguration() {
  try {
    const value = JSON.parse(configNode.textContent);
    if (
      !Array.isArray(value.retrieval_strategies) ||
      !Array.isArray(value.context_strategies) ||
      typeof value.default_retrieval_strategy !== "string" ||
      typeof value.default_context_strategy !== "string"
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

function setBusy(busy, operation = "") {
  form.querySelectorAll("button, input, select, textarea").forEach((control) => {
    control.disabled = busy;
  });
  requestStatus.dataset.state = busy ? "loading" : "ready";
  requestStatus.textContent = busy ? `${operation} in progress…` : "Request complete.";
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

function renderEvidence(evidence) {
  evidenceList.replaceChildren();
  evidence.forEach((hit, index) => {
    const card = document.createElement("article");
    card.className = "evidence-card";
    card.id = evidenceAnchorId(hit.doc_id);

    const heading = document.createElement("div");
    heading.className = "evidence-heading";
    const title = document.createElement("h3");
    title.textContent = `${index + 1}. ${hit.title || "Untitled document"}`;
    const identity = document.createElement("span");
    identity.className = "document-id";
    identity.textContent = `Document ${hit.doc_id}`;
    heading.append(title, identity);

    const score = document.createElement("p");
    score.className = "score";
    score.textContent = `Score ${hit.score.toFixed(6)}`;
    const text = document.createElement("p");
    text.className = "evidence-text";
    text.textContent = hit.text;
    card.append(heading, score, text);
    evidenceList.append(card);
  });
  evidenceCount.textContent = evidence.length === 1 ? "1 document" : `${evidence.length} documents`;
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
  if (isInsufficient !== (payload.citations.length === 0 && payload.evidence.length === 0)) {
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
    } else if (error instanceof Error && error.message === "contract") {
      setFailure(messages.contract);
    } else {
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
