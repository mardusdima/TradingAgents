const ACTIVE_RUN_STATES = new Set(["pending", "validating", "running", "stopping"]);
const STOPPABLE_RUN_STATES = new Set(["pending", "validating", "running"]);
const RUN_STORAGE_KEY = "tradingagents.currentRunId";
const TEAM_ORDER = {
  "Analyst Team": [
    "Market Analyst",
    "Social Analyst",
    "News Analyst",
    "Fundamentals Analyst",
  ],
  "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
  "Trading Team": ["Trader"],
  "Risk Management": [
    "Aggressive Analyst",
    "Neutral Analyst",
    "Conservative Analyst",
  ],
  "Portfolio Management": ["Portfolio Manager"],
};

const REPORT_FINALIZERS = {
  market_report: "Market Analyst",
  sentiment_report: "Social Analyst",
  news_report: "News Analyst",
  fundamentals_report: "Fundamentals Analyst",
  investment_plan: "Research Manager",
  trader_investment_plan: "Trader",
  final_trade_decision: "Portfolio Manager",
};

const PROVIDER_SPECIFIC_FIELDS = {
  google: {
    field: "google_thinking_level",
    label: "Google Thinking Level",
    optionsKey: "google_thinking_levels",
  },
  openai: {
    field: "openai_reasoning_effort",
    label: "OpenAI Reasoning Effort",
    optionsKey: "openai_reasoning_efforts",
  },
  anthropic: {
    field: "anthropic_effort",
    label: "Anthropic Effort",
    optionsKey: "anthropic_efforts",
  },
};

const state = {
  options: null,
  currentSnapshot: createEmptySnapshot(),
  runId: null,
  eventSource: null,
  runStartedAt: null,
  elapsedTimer: null,
  formDraft: {
    provider: null,
    quickModel: null,
    deepModel: null,
    outputLanguage: null,
    providerSpecificValues: {},
  },
};

const elements = {};

document.addEventListener("DOMContentLoaded", () => {
  captureElements();
  bindEvents();
  initializeDashboard().catch((error) => {
    console.error(error);
    showBanner("Failed to load web dashboard options.", "error");
    elements.optionsStatus.textContent = "Load failed";
  });
});

function captureElements() {
  elements.globalBanner = document.getElementById("global-banner");
  elements.optionsStatus = document.getElementById("options-status");
  elements.runStatusChip = document.getElementById("run-status-chip");
  elements.runSummaryText = document.getElementById("run-summary-text");
  elements.runStatusDetail = document.getElementById("run-status-detail");
  elements.activeRunId = document.getElementById("active-run-id");
  elements.exportPathBadge = document.getElementById("export-path-badge");
  elements.startRunButton = document.getElementById("start-run-button");
  elements.stopRunButton = document.getElementById("stop-run-button");
  elements.resetRunButton = document.getElementById("reset-run-button");
  elements.exportRunButton = document.getElementById("export-run-button");
  elements.setupForm = document.getElementById("setup-form");
  elements.tickerInput = document.getElementById("ticker-input");
  elements.analysisDateInput = document.getElementById("analysis-date-input");
  elements.outputLanguageSelect = document.getElementById("output-language-select");
  elements.customLanguageField = document.getElementById("custom-language-field");
  elements.customLanguageInput = document.getElementById("custom-language-input");
  elements.analystOptions = document.getElementById("analyst-options");
  elements.researchDepthSelect = document.getElementById("research-depth-select");
  elements.providerSelect = document.getElementById("provider-select");
  elements.quickModelSelect = document.getElementById("quick-model-select");
  elements.deepModelSelect = document.getElementById("deep-model-select");
  elements.providerSpecificField = document.getElementById("provider-specific-field");
  elements.providerSpecificLabel = document.getElementById("provider-specific-label");
  elements.providerSpecificSelect = document.getElementById("provider-specific-select");
  elements.agentStatusGroups = document.getElementById("agent-status-groups");
  elements.eventFeed = document.getElementById("event-feed");
  elements.toolCallFeed = document.getElementById("tool-call-feed");
  elements.errorBanner = document.getElementById("error-banner");
  elements.currentReport = document.getElementById("current-report");
  elements.compiledReport = document.getElementById("compiled-report");
  elements.finalDecisionCard = document.getElementById("final-decision-card");
  elements.finalDecisionContent = document.getElementById("final-decision-content");
  elements.statAgents = document.getElementById("stat-agents");
  elements.statReports = document.getElementById("stat-reports");
  elements.statLlmCalls = document.getElementById("stat-llm-calls");
  elements.statToolCalls = document.getElementById("stat-tool-calls");
  elements.statTokens = document.getElementById("stat-tokens");
  elements.statElapsed = document.getElementById("stat-elapsed");
}

function bindEvents() {
  elements.setupForm.addEventListener("submit", onStartRun);
  elements.providerSelect.addEventListener("change", onProviderChanged);
  elements.outputLanguageSelect.addEventListener("change", onOutputLanguageChanged);
  elements.stopRunButton.addEventListener("click", onStopRun);
  elements.resetRunButton.addEventListener("click", onResetRun);
  elements.exportRunButton.addEventListener("click", onExportRun);
}

async function initializeDashboard() {
  const [healthResponse, optionsResponse] = await Promise.all([
    fetch("/health"),
    fetch("/api/options"),
  ]);

  if (!healthResponse.ok || !optionsResponse.ok) {
    throw new Error("Failed to load web dashboard options.");
  }

  await healthResponse.json();
  state.options = await optionsResponse.json();
  populateOptions(state.options);
  renderSnapshot(state.currentSnapshot);
  await restoreExistingRunContext();
  elements.optionsStatus.textContent = "Ready";
  if (!state.runId) {
    showBanner("Dashboard ready. Configure a run to begin.", "success");
  }
}

function populateOptions(options) {
  elements.analysisDateInput.value = new Date().toISOString().slice(0, 10);

  populateSelect(
    elements.outputLanguageSelect,
    options.output_languages || [],
    options.defaults.output_language
  );
  populateSelect(
    elements.researchDepthSelect,
    options.research_depths || [],
    String(options.defaults.research_depth)
  );
  populateSelect(
    elements.providerSelect,
    options.providers || [],
    options.defaults.llm_provider
  );

  state.formDraft.provider = options.defaults.llm_provider;
  state.formDraft.quickModel = options.defaults.quick_model;
  state.formDraft.deepModel = options.defaults.deep_model;
  state.formDraft.outputLanguage = options.defaults.output_language;

  elements.tickerInput.value = "SPY";
  renderAnalystOptions(options.analysts || []);
  syncProviderModels();
  syncProviderSpecificField();
  syncCustomLanguageField();
}

function syncFormWithSnapshot(snapshot) {
  const inputs = snapshot?.selected_inputs || {};
  if (!inputs.ticker) {
    return;
  }

  elements.tickerInput.value = inputs.ticker || "";
  elements.analysisDateInput.value = inputs.analysis_date || "";
  elements.researchDepthSelect.value = String(
    inputs.research_depth ?? state.options.defaults.research_depth
  );

  const provider = String(inputs.llm_provider || state.options.defaults.llm_provider);
  elements.providerSelect.value = provider;
  state.formDraft.provider = provider;

  state.formDraft.quickModel = inputs.shallow_thinker || state.options.defaults.quick_model;
  state.formDraft.deepModel = inputs.deep_thinker || state.options.defaults.deep_model;

  syncProviderModels();

  const outputLanguage = inputs.output_language || state.options.defaults.output_language;
  const knownOutputLanguage = (state.options.output_languages || []).some(
    (option) => String(option.value) === String(outputLanguage)
  );
  elements.outputLanguageSelect.value = knownOutputLanguage ? outputLanguage : "custom";
  state.formDraft.outputLanguage = elements.outputLanguageSelect.value;
  syncCustomLanguageField();
  elements.customLanguageInput.value = knownOutputLanguage ? "" : outputLanguage;

  const selectedAnalysts = new Set(inputs.analysts || []);
  for (const node of elements.analystOptions.querySelectorAll('input[name="analysts"]')) {
    node.checked = selectedAnalysts.has(node.value);
  }

  const providerConfig = PROVIDER_SPECIFIC_FIELDS[provider];
  if (providerConfig) {
    state.formDraft.providerSpecificValues[providerConfig.field] =
      inputs[providerConfig.field] || state.formDraft.providerSpecificValues[providerConfig.field];
  }
  syncProviderSpecificField();
}

function populateSelect(select, options, preferredValue) {
  select.innerHTML = "";
  for (const option of options) {
    const node = document.createElement("option");
    node.value = String(option.value);
    node.textContent = option.label;
    if (String(option.value) === String(preferredValue)) {
      node.selected = true;
    }
    select.appendChild(node);
  }
}

function renderAnalystOptions(analysts) {
  elements.analystOptions.innerHTML = "";

  for (const analyst of analysts) {
    const label = document.createElement("label");
    label.className = "checkbox-card";

    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "analysts";
    input.value = analyst.value;
    input.checked = true;

    const copy = document.createElement("span");
    copy.className = "checkbox-copy";
    copy.innerHTML = `<strong>${analyst.label}</strong><span>${analyst.value}</span>`;

    label.appendChild(input);
    label.appendChild(copy);
    elements.analystOptions.appendChild(label);
  }
}

function onProviderChanged() {
  state.formDraft.provider = elements.providerSelect.value;
  state.formDraft.quickModel = elements.quickModelSelect.value;
  state.formDraft.deepModel = elements.deepModelSelect.value;
  syncProviderModels();
  syncProviderSpecificField();
  clearFieldErrors();
}

function onOutputLanguageChanged() {
  state.formDraft.outputLanguage = elements.outputLanguageSelect.value;
  syncCustomLanguageField();
}

function syncCustomLanguageField() {
  const isCustom = elements.outputLanguageSelect.value === "custom";
  elements.customLanguageField.classList.toggle("hidden", !isCustom);
  if (!isCustom) {
    elements.customLanguageInput.value = "";
  }
}

function syncProviderModels() {
  const provider = elements.providerSelect.value;
  const providerModels = (state.options.models_by_provider || {})[provider] || {};
  const quickOptions = providerModels.quick || [];
  const deepOptions = providerModels.deep || [];

  populateSelectWithPreservedValue(
    elements.quickModelSelect,
    quickOptions,
    state.formDraft.quickModel || state.options.defaults.quick_model
  );
  populateSelectWithPreservedValue(
    elements.deepModelSelect,
    deepOptions,
    state.formDraft.deepModel || state.options.defaults.deep_model
  );
}

function populateSelectWithPreservedValue(select, options, preferredValue) {
  select.innerHTML = "";
  let selectedValue = null;

  for (const option of options) {
    const node = document.createElement("option");
    node.value = String(option.value);
    node.textContent = option.label;
    if (selectedValue === null && String(option.value) === String(preferredValue)) {
      node.selected = true;
      selectedValue = String(option.value);
    }
    select.appendChild(node);
  }

  if (selectedValue === null && options.length > 0) {
    select.value = String(options[0].value);
  }
}

function syncProviderSpecificField() {
  const provider = elements.providerSelect.value;
  const config = PROVIDER_SPECIFIC_FIELDS[provider];

  if (!config) {
    elements.providerSpecificField.classList.add("hidden");
    elements.providerSpecificSelect.innerHTML = "";
    return;
  }

  elements.providerSpecificField.classList.remove("hidden");
  elements.providerSpecificLabel.textContent = config.label;

  const options = state.options[config.optionsKey] || [];
  populateSelectWithPreservedValue(
    elements.providerSpecificSelect,
    options,
    state.formDraft.providerSpecificValues[config.field] || options[0]?.value
  );
}

async function onStartRun(event) {
  event.preventDefault();
  clearFieldErrors();
  hideBanner();

  const payload = collectRunPayload();
  const issues = validateFormPayload(payload);
  if (issues.length > 0) {
    applyValidationIssues(issues);
    showBanner("Please fix the highlighted fields before starting the run.", "error");
    return;
  }

  setBusyState(true);

  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();

    if (!response.ok) {
      if (response.status === 409) {
        await restoreExistingRunContext();
        showBanner(
          "An active run was already in progress, so the dashboard reconnected to it.",
          "error"
        );
        return;
      }
      if (body?.detail?.issues) {
        applyValidationIssues(body.detail.issues);
      }
      showBanner(body?.detail?.message || "Failed to start run.", "error");
      setBusyState(false);
      return;
    }

    state.runId = body.session_id;
    persistRunId(state.runId);
    state.runStartedAt = Date.now();
    renderSnapshot(body);
    startElapsedTimer();
    connectEventStream(body.session_id);
    showBanner("Run started. Live updates are streaming in.", "success");
  } catch (error) {
    console.error(error);
    showBanner("Network error while starting the run.", "error");
    setBusyState(false);
  }
}

function collectRunPayload() {
  const analysts = Array.from(
    elements.analystOptions.querySelectorAll('input[name="analysts"]:checked')
  ).map((node) => node.value);
  const provider = elements.providerSelect.value;
  const providerOption = (state.options.providers || []).find(
    (option) => String(option.value) === String(provider)
  );
  const payload = {
    ticker: elements.tickerInput.value.trim(),
    analysis_date: elements.analysisDateInput.value,
    analysts,
    research_depth: Number(elements.researchDepthSelect.value),
    llm_provider: provider,
    backend_url: providerOption ? providerOption.backend_url : "",
    shallow_thinker: elements.quickModelSelect.value,
    deep_thinker: elements.deepModelSelect.value,
    output_language:
      elements.outputLanguageSelect.value === "custom"
        ? elements.customLanguageInput.value.trim()
        : elements.outputLanguageSelect.value,
  };

  const providerConfig = PROVIDER_SPECIFIC_FIELDS[provider];
  if (providerConfig) {
    payload[providerConfig.field] = elements.providerSpecificSelect.value;
    state.formDraft.providerSpecificValues[providerConfig.field] =
      elements.providerSpecificSelect.value;
  }

  state.formDraft.quickModel = payload.shallow_thinker;
  state.formDraft.deepModel = payload.deep_thinker;
  state.formDraft.outputLanguage = elements.outputLanguageSelect.value;
  return payload;
}

function validateFormPayload(payload) {
  const issues = [];
  const today = new Date().toISOString().slice(0, 10);

  if (!payload.ticker) {
    issues.push({ field: "ticker", message: "Ticker is required." });
  }
  if (!payload.analysis_date) {
    issues.push({ field: "analysis_date", message: "Analysis date is required." });
  } else if (payload.analysis_date > today) {
    issues.push({
      field: "analysis_date",
      message: "Analysis date cannot be in the future.",
    });
  }
  if (payload.analysts.length === 0) {
    issues.push({
      field: "analysts",
      message: "Select at least one analyst.",
    });
  }
  if (!payload.shallow_thinker) {
    issues.push({
      field: "shallow_thinker",
      message: "Choose a quick-thinking model.",
    });
  }
  if (!payload.deep_thinker) {
    issues.push({
      field: "deep_thinker",
      message: "Choose a deep-thinking model.",
    });
  }
  if (!payload.output_language) {
    issues.push({
      field: "output_language",
      message: "Output language is required.",
    });
  }
  return issues;
}

function applyValidationIssues(issues) {
  for (const issue of issues) {
    const node = document.getElementById(`${issue.field}-error`);
    if (node) {
      node.textContent = issue.message;
    }
  }
}

function clearFieldErrors() {
  for (const node of document.querySelectorAll(".field-error")) {
    node.textContent = "";
  }
}

function connectEventStream(sessionId) {
  closeEventStream();
  state.eventSource = new EventSource(`/api/runs/${sessionId}/events`);

  state.eventSource.addEventListener("snapshot", (event) => {
    try {
      const snapshot = JSON.parse(event.data);
      renderSnapshot(snapshot);
      const done = !ACTIVE_RUN_STATES.has(snapshot.status);
      if (done) {
        setBusyState(false);
        stopElapsedTimer();
      }
    } catch (error) {
      console.error(error);
      showBanner("Failed to read streamed snapshot update.", "error");
    }
  });

  state.eventSource.onerror = () => {
    if (!state.currentSnapshot || ACTIVE_RUN_STATES.has(state.currentSnapshot.status)) {
      showBanner("Live event stream disconnected.", "error");
    }
    closeEventStream();
  };
}

function closeEventStream() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

function renderSnapshot(snapshot) {
  state.currentSnapshot = snapshot || createEmptySnapshot();
  state.runId = state.currentSnapshot.session_id || state.runId;
  if (state.runId) {
    persistRunId(state.runId);
  }

  const status = state.currentSnapshot.status || "pending";
  setStatusChip(status);
  renderSummary(status);
  renderErrors(state.currentSnapshot.errors || []);
  renderAgentStatuses(state.currentSnapshot.agent_statuses || []);
  renderEventFeed(state.currentSnapshot.events || []);
  renderToolCalls(state.currentSnapshot.tool_calls || []);
  renderReports(state.currentSnapshot);
  renderStats(state.currentSnapshot);
  setBusyState(Boolean(state.runId) && ACTIVE_RUN_STATES.has(status));
  elements.activeRunId.textContent = state.runId ? `Session ${state.runId.slice(0, 8)}` : "No session";
  elements.exportPathBadge.textContent =
    state.currentSnapshot.export_info?.report_path || "Not exported";
  elements.exportRunButton.disabled = !(status === "completed" && state.runId);
  elements.stopRunButton.disabled = !(state.runId && STOPPABLE_RUN_STATES.has(status));
}

function setStatusChip(status) {
  elements.runStatusChip.textContent = capitalize(status);
  elements.runStatusChip.className = `status-chip status-${status}`;
}

function renderSummary(status) {
  const inputs = state.currentSnapshot.selected_inputs || {};
  if (!inputs.ticker || !inputs.analysis_date) {
    elements.runSummaryText.textContent = "No active analysis";
    elements.runStatusDetail.textContent = "";
    elements.runStatusDetail.classList.add("hidden");
    return;
  }

  elements.runSummaryText.textContent = `${inputs.ticker} on ${inputs.analysis_date} · ${capitalize(status)}`;
  if (status === "stopping") {
    elements.runStatusDetail.textContent =
      "Waiting for the current LLM or tool call to finish before the run can cancel.";
    elements.runStatusDetail.classList.remove("hidden");
    return;
  }

  elements.runStatusDetail.textContent = "";
  elements.runStatusDetail.classList.add("hidden");
}

function renderErrors(errors) {
  if (!errors || errors.length === 0) {
    elements.errorBanner.classList.add("hidden");
    elements.errorBanner.textContent = "";
    return;
  }

  elements.errorBanner.classList.remove("hidden");
  elements.errorBanner.textContent = errors.map((error) => error.message).join(" ");
}

function renderAgentStatuses(agentStatuses) {
  if (!agentStatuses.length) {
    elements.agentStatusGroups.className = "status-groups empty-state";
    elements.agentStatusGroups.textContent = "Start a run to watch team progression.";
    return;
  }

  const statusMap = Object.fromEntries(agentStatuses.map((item) => [item.name, item.status]));
  elements.agentStatusGroups.className = "status-groups";
  elements.agentStatusGroups.innerHTML = "";

  for (const [teamName, agents] of Object.entries(TEAM_ORDER)) {
    const presentAgents = agents.filter((agent) => statusMap[agent]);
    if (!presentAgents.length) {
      continue;
    }

    const group = document.createElement("section");
    group.className = "status-group";

    const title = document.createElement("h4");
    title.textContent = teamName;
    group.appendChild(title);

    const list = document.createElement("div");
    list.className = "status-list";

    for (const agent of presentAgents) {
      const row = document.createElement("div");
      row.className = "status-row";
      row.innerHTML = `
        <span class="status-name">${agent}</span>
        <span class="inline-badge status-${statusMap[agent]}">${capitalize(statusMap[agent])}</span>
      `;
      list.appendChild(row);
    }

    group.appendChild(list);
    elements.agentStatusGroups.appendChild(group);
  }
}

function renderEventFeed(events) {
  if (!events.length) {
    renderEmptyList(elements.eventFeed, "No events yet.");
    return;
  }

  const items = events.slice(-14).reverse();
  renderFeed(elements.eventFeed, items.map((event) => ({
    timestamp: event.timestamp || "--:--:--",
    label: [event.source, event.event_type].filter(Boolean).join(" · "),
    body: summarizeEvent(event),
  })));
}

function renderToolCalls(toolCalls) {
  if (!toolCalls.length) {
    renderEmptyList(elements.toolCallFeed, "No tool calls yet.");
    return;
  }

  const items = toolCalls.slice(-10).reverse();
  renderFeed(elements.toolCallFeed, items.map((toolCall) => ({
    timestamp: toolCall.timestamp || "--:--:--",
    label: toolCall.source || "Tool",
    body: `${toolCall.tool_name}\n${formatValue(toolCall.arguments)}`,
  })));
}

function renderFeed(node, items) {
  node.className = "feed-list";
  node.innerHTML = "";
  for (const item of items) {
    const entry = document.createElement("li");
    entry.className = "feed-item";
    entry.innerHTML = `
      <div class="feed-head">
        <span>${escapeHtml(item.label)}</span>
        <span>${escapeHtml(item.timestamp)}</span>
      </div>
      <div class="feed-body">${escapeHtml(item.body)}</div>
    `;
    node.appendChild(entry);
  }
}

function renderEmptyList(node, message) {
  node.className = "feed-list empty-state";
  node.innerHTML = `<li>${escapeHtml(message)}</li>`;
}

function renderReports(snapshot) {
  const currentReport = snapshot.current_report || "Waiting for analysis report...";
  const compiledReport =
    snapshot.compiled_report ||
    "The compiled report will appear here when enough sections are ready.";

  elements.currentReport.textContent = currentReport;
  elements.compiledReport.textContent = compiledReport;

  const finalDecision =
    snapshot.structured_report_sections?.final_trade_decision ||
    snapshot.report_sections?.final_trade_decision ||
    "";
  if (finalDecision) {
    elements.finalDecisionCard.classList.remove("hidden");
    elements.finalDecisionContent.textContent = finalDecision;
  } else {
    elements.finalDecisionCard.classList.add("hidden");
    elements.finalDecisionContent.textContent = "";
  }
}

function renderStats(snapshot) {
  const agentStatuses = snapshot.agent_statuses || [];
  const completedAgents = agentStatuses.filter((item) => item.status === "completed").length;
  const reportSections = snapshot.report_sections || {};

  elements.statAgents.textContent = `${completedAgents}/${agentStatuses.length}`;
  elements.statReports.textContent = `${countCompletedReports(snapshot)}/${Object.keys(reportSections).length}`;
  elements.statLlmCalls.textContent = String(snapshot.stats?.llm_calls || 0);
  elements.statToolCalls.textContent = String(snapshot.stats?.tool_calls || 0);

  const promptTokens = snapshot.stats?.prompt_tokens || 0;
  const completionTokens = snapshot.stats?.completion_tokens || 0;
  elements.statTokens.textContent =
    promptTokens || completionTokens
      ? `${formatCompactNumber(promptTokens)}↑ ${formatCompactNumber(completionTokens)}↓`
      : "--";
}

function countCompletedReports(snapshot) {
  const statuses = Object.fromEntries((snapshot.agent_statuses || []).map((item) => [item.name, item.status]));
  let count = 0;
  for (const [sectionName, content] of Object.entries(snapshot.report_sections || {})) {
    const finalizer = REPORT_FINALIZERS[sectionName];
    if (content && finalizer && statuses[finalizer] === "completed") {
      count += 1;
    }
  }
  return count;
}

function startElapsedTimer() {
  stopElapsedTimer();
  updateElapsedTime();
  state.elapsedTimer = window.setInterval(updateElapsedTime, 1000);
}

function stopElapsedTimer() {
  if (state.elapsedTimer) {
    window.clearInterval(state.elapsedTimer);
    state.elapsedTimer = null;
  }
}

function updateElapsedTime() {
  if (!state.runStartedAt) {
    elements.statElapsed.textContent = "00:00";
    return;
  }

  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - state.runStartedAt) / 1000));
  const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");
  elements.statElapsed.textContent = `${minutes}:${seconds}`;
}

function setBusyState(isBusy) {
  const controls = elements.setupForm.querySelectorAll("input, select, button");
  controls.forEach((control) => {
    control.disabled = isBusy;
  });
  elements.startRunButton.disabled = isBusy;
  elements.stopRunButton.disabled = !(
    state.runId && STOPPABLE_RUN_STATES.has(state.currentSnapshot.status)
  );
  elements.resetRunButton.disabled = isBusy;
  elements.exportRunButton.disabled = !(state.currentSnapshot.status === "completed" && state.runId);
}

async function onStopRun() {
  if (!state.runId || !STOPPABLE_RUN_STATES.has(state.currentSnapshot.status)) {
    showBanner("There is no active run to stop.", "error");
    return;
  }

  try {
    const response = await fetch(`/api/runs/${state.runId}/stop`, { method: "POST" });
    const body = await response.json();
    if (!response.ok) {
      showBanner(body?.detail?.message || "Failed to stop the current run.", "error");
      return;
    }

    renderSnapshot(body);
    showBanner(
      "Stop requested. The run will stop after the current step yields control.",
      "success"
    );
    elements.stopRunButton.disabled = true;
  } catch (error) {
    console.error(error);
    showBanner("Network error while trying to stop the run.", "error");
  }
}

async function onExportRun() {
  if (!state.runId) {
    showBanner("No completed run is available to export.", "error");
    return;
  }

  try {
    const response = await fetch(`/api/runs/${state.runId}/export`, { method: "POST" });
    const body = await response.json();
    if (!response.ok) {
      showBanner(body?.detail?.message || "Export failed.", "error");
      return;
    }

    elements.exportPathBadge.textContent = body.report_path;
    showBanner(`Report exported to ${body.report_path}`, "success");

    const snapshotResponse = await fetch(`/api/runs/${state.runId}`);
    if (snapshotResponse.ok) {
      renderSnapshot(await snapshotResponse.json());
    }
  } catch (error) {
    console.error(error);
    showBanner("Network error while exporting the report.", "error");
  }
}

function onResetRun() {
  if (state.runId && ACTIVE_RUN_STATES.has(state.currentSnapshot.status)) {
    showBanner(
      "A run is still active. Wait for it to finish or refresh to reconnect.",
      "error"
    );
    return;
  }

  closeEventStream();
  stopElapsedTimer();
  state.currentSnapshot = createEmptySnapshot();
  state.runId = null;
  state.runStartedAt = null;
  clearStoredRunId();
  elements.setupForm.reset();
  clearFieldErrors();
  hideBanner();

  if (state.options) {
    populateOptions(state.options);
  }

  renderSnapshot(state.currentSnapshot);
  showBanner("Dashboard reset. Configure a new analysis when you are ready.", "success");
}

async function restoreExistingRunContext() {
  const storedRunId = loadStoredRunId();
  if (storedRunId) {
    const restored = await restoreRunById(storedRunId);
    if (restored) {
      return true;
    }
    clearStoredRunId();
  }

  try {
    const response = await fetch("/api/runs/active");
    if (!response.ok) {
      return false;
    }
    const snapshot = await response.json();
    applyRestoredSnapshot(snapshot);
    showBanner("Reconnected to the active run.", "success");
    return true;
  } catch (error) {
    console.error(error);
    return false;
  }
}

async function restoreRunById(runId) {
  try {
    const response = await fetch(`/api/runs/${runId}`);
    if (!response.ok) {
      return false;
    }
    const snapshot = await response.json();
    applyRestoredSnapshot(snapshot);
    showBanner("Restored the previous dashboard session.", "success");
    return true;
  } catch (error) {
    console.error(error);
    return false;
  }
}

function applyRestoredSnapshot(snapshot) {
  state.runId = snapshot.session_id || null;
  persistRunId(state.runId);
  syncFormWithSnapshot(snapshot);
  renderSnapshot(snapshot);
  if (state.runId && ACTIVE_RUN_STATES.has(snapshot.status)) {
    state.runStartedAt = Date.now();
    startElapsedTimer();
    connectEventStream(state.runId);
  } else {
    stopElapsedTimer();
  }
}

function showBanner(message, tone) {
  elements.globalBanner.textContent = message;
  elements.globalBanner.className = `banner ${tone || ""}`;
}

function hideBanner() {
  elements.globalBanner.className = "banner hidden";
  elements.globalBanner.textContent = "";
}

function summarizeEvent(event) {
  const payload = event.payload || {};
  if (event.event_type === "message") {
    return payload.content || "Message received";
  }
  if (event.event_type === "tool_call") {
    return `${payload.tool_name || "Tool"} ${formatValue(payload.arguments)}`;
  }
  if (event.event_type === "report_update") {
    return `Updated ${payload.section || "report section"}`;
  }
  if (event.event_type === "status_change") {
    return `Status changed to ${payload.status || "unknown"}`;
  }
  return formatValue(payload) || event.event_type;
}

function formatValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    return String(value);
  }
}

function formatCompactNumber(value) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return String(value);
}

function capitalize(value) {
  return String(value || "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function createEmptySnapshot() {
  return {
    status: "idle",
    agent_statuses: [],
    events: [],
    messages: [],
    tool_calls: [],
    report_sections: {},
    structured_report_sections: {},
    stats: {
      llm_calls: 0,
      tool_calls: 0,
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
    },
    export_info: {
      report_path: null,
      log_path: null,
    },
    errors: [],
    selected_inputs: {},
  };
}

function persistRunId(runId) {
  if (!runId) {
    return;
  }
  window.localStorage.setItem(RUN_STORAGE_KEY, runId);
}

function loadStoredRunId() {
  return window.localStorage.getItem(RUN_STORAGE_KEY);
}

function clearStoredRunId() {
  window.localStorage.removeItem(RUN_STORAGE_KEY);
}
