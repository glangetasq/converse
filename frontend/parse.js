(() => {
  const LINKEDIN_MESSAGING_PARSER_ID = "linkedin-messaging";
  const EVAL_EXAMPLES_ENDPOINT = "http://localhost:3000/api/eval_examples";
  const CURRENT_USER_STORAGE_KEY = "current_user";
  const SELF_SENDER_NAME = "Quentin Glangetas";
  const SELF_RATING_LABELS = ["very poor", "poor", "neutral", "good", "very good"];
  const OTHER_RATING_LABELS = ["unhelpful", "confused", "neutral", "good", "very good"];
  const PARSE_RETRY_DELAY_MS = 250;
  const PARSE_RETRY_TIMEOUT_MS = 3500;
  const PARSER_FILES = [
    "frontend/content/parsing/runtime.js",
    "frontend/content/parsing/helpers.js",
    "frontend/content/parsing/execute.js",
    "frontend/content/parsing/parsers/linkedin-messaging.js"
  ];

  const refreshButton = document.getElementById("refresh-button");
  const saveExampleButton = document.getElementById("save-example-button");
  const saveExampleButtonLabel = saveExampleButton?.querySelector(".button-label");
  const statusPill = document.getElementById("status-pill");
  const sourceLabel = document.getElementById("source-label");
  const statePanel = document.getElementById("state-panel");
  const summaryPanel = document.getElementById("summary-panel");
  const parseOutput = document.getElementById("parse-output");

  const urlParams = new URLSearchParams(window.location.search);
  const sourceTabIdValue = urlParams.get("sourceTabId");
  const state = {
    sourceUrl: urlParams.get("sourceUrl") || "",
    sourceTabId: sourceTabIdValue === null ? Number.NaN : Number(sourceTabIdValue),
    messageSelections: [],
    parseResult: null,
    parseSequence: 0,
    saveSequence: 0
  };

  function updateUrlState() {
    const params = new URLSearchParams();

    if (state.sourceUrl) {
      params.set("sourceUrl", state.sourceUrl);
    }

    if (Number.isInteger(state.sourceTabId)) {
      params.set("sourceTabId", String(state.sourceTabId));
    }

    window.history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
  }

  function getSourceDisplayText() {
    if (!state.sourceUrl) {
      return Number.isInteger(state.sourceTabId)
        ? `source tab ${state.sourceTabId}`
        : "source tab unavailable";
    }

    try {
      const parsed = new URL(state.sourceUrl);
      return `${parsed.hostname}${parsed.pathname}`;
    } catch (_error) {
      return state.sourceUrl;
    }
  }

  function setSourceLabel() {
    sourceLabel.textContent = getSourceDisplayText();
    sourceLabel.title = state.sourceUrl || sourceLabel.textContent;
  }

  function setStatus(label, tone = "muted") {
    statusPill.textContent = label;
    statusPill.classList.toggle("is-success", tone === "success");
    statusPill.classList.toggle("is-error", tone === "error");
  }

  function setStatePanel(message, tone = "muted") {
    statePanel.hidden = !message;
    statePanel.textContent = message || "";
    statePanel.classList.toggle("is-error", tone === "error");
  }

  function setLoadingState() {
    setStatus("parsing");
    setStatePanel("Parsing the source tab...");
    summaryPanel.hidden = true;
    summaryPanel.replaceChildren();
    parseOutput.replaceChildren();
    updateSaveExampleButton({ forceDisabled: true });
  }

  function normalizeErrorMessage(value, fallback = "Something went wrong.") {
    if (typeof value !== "string") {
      return fallback;
    }

    const normalized = value.replace(/\s+/g, " ").trim();
    return normalized || fallback;
  }

  async function parseSourceTab() {
    if (!Number.isInteger(state.sourceTabId)) {
      return {
        status: "failed_to_parse_with_appropriate_methodology",
        error: "Source tab id is unavailable."
      };
    }

    await chrome.scripting.executeScript({
      target: { tabId: state.sourceTabId },
      files: PARSER_FILES
    });

    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: state.sourceTabId },
      func: async (parserIdOverride, retryDelayMs, retryTimeoutMs) => {
        if (!globalThis.ConverseParsing?.parseCurrentPageWithRetry) {
          return {
            status: "failed_to_parse_with_appropriate_methodology",
            error: "Parser runtime is unavailable on the current page."
          };
        }

        return globalThis.ConverseParsing.parseCurrentPageWithRetry(
          parserIdOverride,
          retryDelayMs,
          retryTimeoutMs
        );
      },
      args: [LINKEDIN_MESSAGING_PARSER_ID, PARSE_RETRY_DELAY_MS, PARSE_RETRY_TIMEOUT_MS]
    });

    return result;
  }

  function normalizeParseResult(parseResult) {
    if (!parseResult || typeof parseResult !== "object") {
      return {
        status: "failed_to_parse_with_appropriate_methodology",
        error: "No parse result is available."
      };
    }

    const normalized = { ...parseResult };
    if (typeof normalized.output === "string") {
      try {
        normalized.output = JSON.parse(normalized.output);
      } catch (_error) {
        normalized.output = normalized.output.trim();
      }
    }

    return normalized;
  }

  function formatJson(value) {
    return JSON.stringify(value, null, 2) ?? String(value);
  }

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function normalizeName(value) {
    return String(value ?? "")
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  function isSelfSender(sender) {
    return normalizeName(sender) === normalizeName(SELF_SENDER_NAME);
  }

  function getRatingLabels(item) {
    return isSelfSender(item?.sender) ? SELF_RATING_LABELS : OTHER_RATING_LABELS;
  }

  function getDefaultCategory(item, index) {
    return index === 0 && isSelfSender(item?.sender) ? "intro" : "message";
  }

  function isMessageIncluded(selection) {
    return selection?.included !== false;
  }

  function createMetaPill(value) {
    const pill = document.createElement("span");
    pill.className = "meta-pill";
    pill.textContent = value;
    return pill;
  }

  function createBlockHeader(title, countText = "") {
    const header = document.createElement("div");
    header.className = "block-header";

    const heading = document.createElement("h2");
    heading.className = "block-title";
    heading.textContent = title;
    header.append(heading);

    if (countText) {
      const count = document.createElement("span");
      count.className = "block-count";
      count.textContent = countText;
      header.append(count);
    }

    return header;
  }

  function createCategoryControl(item, index, selection) {
    const control = document.createElement("section");
    control.className = "message-control";

    const label = document.createElement("p");
    label.className = "control-label";
    label.textContent = "category";

    const group = document.createElement("div");
    group.className = "category-button-group";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", `category for message ${index + 1}`);

    const buttons = ["intro", "message"].map((category) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "category-button";
      button.textContent = category;
      button.dataset.category = category;
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => {
        selection.category = category;
        update();
      });
      group.append(button);
      return button;
    });

    function update() {
      control.dataset.value = selection.category;
      buttons.forEach((button) => {
        const isSelected = button.dataset.category === selection.category;
        button.classList.toggle("is-selected", isSelected);
        button.setAttribute("aria-pressed", String(isSelected));
      });
    }

    update();
    control.append(label, group);
    return control;
  }

  function getRatingLabel(labels, rating) {
    return labels[rating - 1] ?? "neutral";
  }

  function getParsedMessageOutput() {
    const output = isPlainObject(state.parseResult?.output) ? state.parseResult.output : null;
    return Array.isArray(output?.messages) ? output : null;
  }

  function getIncludedMessageCount(output = getParsedMessageOutput()) {
    if (!output) {
      return 0;
    }

    return output.messages.filter((_message, index) => (
      isMessageIncluded(state.messageSelections[index])
    )).length;
  }

  function canSaveExample() {
    return state.parseResult?.status === "success"
      && state.parseResult?.parserId === LINKEDIN_MESSAGING_PARSER_ID
      && Boolean(getParsedMessageOutput())
      && getIncludedMessageCount() > 0;
  }

  function updateSaveExampleButton({ label = "Save Example", forceDisabled = false } = {}) {
    if (!saveExampleButton) {
      return;
    }

    if (saveExampleButtonLabel) {
      saveExampleButtonLabel.textContent = label;
    }

    saveExampleButton.disabled = forceDisabled || !canSaveExample();
    saveExampleButton.classList.toggle("is-busy", label === "Saving");
  }

  function createProcessingControl(_item, index, selection, onChange) {
    const control = document.createElement("section");
    control.className = "message-control processing-control";

    const label = document.createElement("p");
    label.className = "control-label";
    label.textContent = "api eval";

    const button = document.createElement("button");
    button.type = "button";
    button.className = "switch-button";

    const track = document.createElement("span");
    track.className = "switch-track";
    track.setAttribute("aria-hidden", "true");

    const knob = document.createElement("span");
    knob.className = "switch-knob";
    track.append(knob);

    const text = document.createElement("span");
    text.className = "switch-button-label";

    button.append(track, text);
    button.addEventListener("click", () => {
      selection.included = !isMessageIncluded(selection);
      update();
      onChange?.();
    });

    function update() {
      const included = isMessageIncluded(selection);
      control.dataset.value = included ? "process" : "ignore";
      button.classList.toggle("is-on", included);
      button.setAttribute("aria-pressed", String(included));
      button.setAttribute(
        "aria-label",
        included
          ? `message ${index + 1} will be processed`
          : `message ${index + 1} will be ignored`
      );
      button.title = included ? "processed" : "ignored";
      text.textContent = included ? "process" : "ignore";
    }

    update();
    control.append(label, button);
    return control;
  }

  function createRatingControl(item, index, selection) {
    const labels = getRatingLabels(item);
    let previewRating = null;

    const control = document.createElement("section");
    control.className = "message-control rating-control";

    const labelRow = document.createElement("div");
    labelRow.className = "rating-label-row";

    const label = document.createElement("p");
    label.className = "control-label";
    label.textContent = "message rating";

    const liveLabel = document.createElement("span");
    liveLabel.className = "rating-live-label";
    liveLabel.setAttribute("aria-live", "polite");

    labelRow.append(label, liveLabel);

    const ratingGroup = document.createElement("div");
    ratingGroup.className = "star-rating";
    ratingGroup.setAttribute("role", "group");
    ratingGroup.setAttribute("aria-label", `rating for message ${index + 1}`);

    const starButtons = [];
    for (let rating = 1; rating <= 5; rating += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "star-button";
      button.textContent = "★";
      button.dataset.rating = String(rating);
      button.title = labels[rating - 1];
      button.setAttribute("aria-label", `set message ${index + 1} rating to ${rating}: ${labels[rating - 1]}`);
      button.addEventListener("mouseenter", () => updatePreview(rating));
      button.addEventListener("focus", () => updatePreview(rating));
      button.addEventListener("mouseleave", clearPreview);
      button.addEventListener("blur", clearPreview);
      button.addEventListener("click", () => setRating(rating));
      starButtons.push(button);
      ratingGroup.append(button);
    }

    function render() {
      const activeRating = previewRating ?? selection.rating;
      control.dataset.value = String(selection.rating);
      liveLabel.textContent = getRatingLabel(labels, activeRating);
      liveLabel.classList.toggle("is-previewing", previewRating !== null);
      starButtons.forEach((button) => {
        const rating = Number(button.dataset.rating);
        button.classList.toggle("is-selected", rating <= activeRating);
        button.classList.toggle("is-previewing", previewRating !== null && rating <= activeRating);
        button.setAttribute("aria-pressed", String(selection.rating === rating));
      });
    }

    function setRating(nextRating) {
      selection.rating = nextRating;
      previewRating = null;
      render();
    }

    function updatePreview(nextRating) {
      previewRating = nextRating;
      render();
    }

    function clearPreview() {
      previewRating = null;
      render();
    }

    render();
    control.append(labelRow, ratingGroup);
    return control;
  }

  function setMessageProcessingState(row, selection) {
    const included = isMessageIncluded(selection);
    row.classList.toggle("is-ignored-message", !included);
    row.querySelectorAll(".category-button, .star-button").forEach((button) => {
      button.disabled = !included;
    });
  }

  function createMessageControls(item, index, selection, onProcessingChange) {
    const controls = document.createElement("aside");
    controls.className = "message-controls";
    controls.append(
      createProcessingControl(item, index, selection, onProcessingChange),
      createCategoryControl(item, index, selection),
      createRatingControl(item, index, selection)
    );
    return controls;
  }

  function renderMessageItem(item, index) {
    const messageRecord = isPlainObject(item) ? item : { message: String(item ?? "") };
    const selection = {
      included: true,
      category: getDefaultCategory(messageRecord, index),
      rating: 3
    };
    state.messageSelections[index] = selection;

    const row = document.createElement("article");
    row.className = "array-item message-item";
    row.classList.toggle("is-self-message", isSelfSender(messageRecord.sender));

    const main = document.createElement("div");
    main.className = "array-item-main";

    const title = document.createElement("p");
    title.className = "array-item-title";
    title.textContent = `message ${index + 1}`;
    main.append(title);

    const meta = document.createElement("div");
    meta.className = "message-meta";
    const datetime = messageRecord.datetime
      || [messageRecord.date, messageRecord.time].filter(Boolean).join(" ");
    [
      ["sender", messageRecord.sender],
      ["datetime", datetime]
    ].forEach(([key, value]) => {
      if (value) {
        meta.append(createMetaPill(`${key}: ${value}`));
      }
    });

    if (meta.children.length > 0) {
      main.append(meta);
    }

    const message = document.createElement("pre");
    message.className = "message-text";
    message.textContent = String(messageRecord.message ?? "").trim() || "(empty)";
    main.append(message);

    const extraEntries = Object.entries(messageRecord).filter(([key]) => !["sender", "date", "time", "datetime", "message"].includes(key));
    if (extraEntries.length > 0) {
      const extra = document.createElement("pre");
      extra.className = "json-pre";
      extra.textContent = formatJson(Object.fromEntries(extraEntries));
      main.append(extra);
    }

    const controls = createMessageControls(messageRecord, index, selection, () => {
      setMessageProcessingState(row, selection);
      updateSaveExampleButton();
    });

    row.append(main, controls);
    setMessageProcessingState(row, selection);

    return row;
  }

  function renderMessageArray(values) {
    state.messageSelections = [];

    const block = document.createElement("section");
    block.className = "array-block";
    block.append(createBlockHeader("messages", `${values.length} items`));

    if (values.length === 0) {
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "empty array";
      block.append(empty);
      return block;
    }

    const scroll = document.createElement("div");
    scroll.className = "array-scroll";
    values.forEach((item, index) => {
      scroll.append(renderMessageItem(item, index));
    });

    block.append(scroll);
    return block;
  }

  function renderRawResult(value) {
    const block = document.createElement("section");
    block.className = "scalar-block";
    block.append(createBlockHeader("raw result"));

    const pre = document.createElement("pre");
    pre.className = "json-pre";
    pre.textContent = formatJson(value);
    block.append(pre);
    return block;
  }

  function renderSummary(parseResult) {
    summaryPanel.replaceChildren();
    summaryPanel.hidden = false;

    const chips = [
      `status: ${parseResult.status ?? "unknown"}`,
      `parser: ${LINKEDIN_MESSAGING_PARSER_ID}`
    ];

    const output = isPlainObject(parseResult.output) ? parseResult.output : null;
    if (output?.name) {
      chips.push(`participant: ${output.name}`);
    }

    if (Array.isArray(output?.messages)) {
      chips.push(`messages: ${output.messages.length}`);
    }

    if (parseResult.url) {
      try {
        const parsed = new URL(parseResult.url);
        chips.push(`url: ${parsed.hostname}`);
      } catch (_error) {
        chips.push("url: present");
      }
    }

    chips.forEach((label) => {
      summaryPanel.append(createMetaPill(label));
    });
  }

  function renderParseResult(parseResult) {
    const normalized = normalizeParseResult(parseResult);
    state.parseResult = normalized;
    parseOutput.replaceChildren();
    renderSummary(normalized);

    if (normalized.status !== "success") {
      setStatus("failed", "error");
      setStatePanel(normalizeErrorMessage(normalized.error, "Parsing did not succeed."), "error");
      parseOutput.append(renderRawResult(normalized));
      updateSaveExampleButton();
      return;
    }

    if (normalized.parserId !== LINKEDIN_MESSAGING_PARSER_ID) {
      setStatus("wrong parser", "error");
      setStatePanel("This lookup window only supports LinkedIn message threads.", "error");
      parseOutput.append(renderRawResult(normalized));
      updateSaveExampleButton();
      return;
    }

    const output = isPlainObject(normalized.output) ? normalized.output : null;
    if (!Array.isArray(output?.messages)) {
      setStatus("no messages", "error");
      setStatePanel("LinkedIn parsing succeeded, but no message array was returned.", "error");
      parseOutput.append(renderRawResult(normalized));
      updateSaveExampleButton();
      return;
    }

    setStatus("parsed", "success");
    setStatePanel("");
    parseOutput.append(renderMessageArray(output.messages));
    updateSaveExampleButton();
  }

  async function getStoredCurrentUser() {
    const stored = await chrome.storage.local.get([CURRENT_USER_STORAGE_KEY]);
    const userName = String(stored[CURRENT_USER_STORAGE_KEY] ?? "").trim();

    if (!userName) {
      throw new Error("Sign in before saving an eval example.");
    }

    return {
      userName
    };
  }

  function buildEvalExamplePayload(currentUser) {
    const output = getParsedMessageOutput();
    if (!output) {
      throw new Error("No parsed messages are available to save.");
    }

    const recipientName = inferRecipientName(output, currentUser.userName);
    const messages = output.messages.flatMap((message, index) => {
      const selection = state.messageSelections[index] ?? {};
      if (!isMessageIncluded(selection)) {
        return [];
      }

      const rating = Number(selection.rating ?? 3);
      const category = selection.category ?? getDefaultCategory(message, index);
      const sentTime = message.datetime
        || [message.date, message.time].filter(Boolean).join(" ")
        || null;

      return [{
        message_order: index,
        sender_name: String(message.sender ?? "").trim(),
        sentTime: normalizeEvalMessageTime(sentTime),
        body: String(message.message ?? "").trim(),
        category,
        rating
      }];
    });

    if (messages.length === 0) {
      throw new Error("Turn on at least one message before saving an eval example.");
    }

    return {
      saved_at: new Date().toISOString(),
      user_name: currentUser.userName,
      recipient_name: recipientName,
      source: "linkedin",
      messages
    };
  }

  function inferRecipientName(output, userName) {
    const userNameKey = normalizeName(userName);
    const senderCounts = new Map();

    output.messages.forEach((message, index) => {
      const senderName = String(message?.sender ?? "").trim();
      const senderKey = normalizeName(senderName);

      if (!senderName || !senderKey || senderKey === userNameKey) {
        return;
      }

      const entry = senderCounts.get(senderKey) ?? {
        count: 0,
        firstIndex: index,
        name: senderName
      };
      entry.count += 1;
      senderCounts.set(senderKey, entry);
    });

    const [bestSender] = Array.from(senderCounts.values()).sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }

      return left.firstIndex - right.firstIndex;
    });

    if (bestSender) {
      return bestSender.name;
    }

    const parsedParticipantName = String(output.name ?? "").trim();
    if (parsedParticipantName && normalizeName(parsedParticipantName) !== userNameKey) {
      return parsedParticipantName;
    }

    throw new Error("Unable to infer the recipient name from this conversation.");
  }

  function normalizeEvalMessageTime(value) {
    const text = String(value ?? "").replace(/\s+/g, " ").trim();
    if (!text) {
      return null;
    }

    const compactMatch = text.match(/^(?:sun|mon|tue|wed|thu|fri|sat)(\d{1,2})([a-z]{3})(\d{2}|\d{4})\s+(\d{1,2})(?::(\d{2}))?\s*([ap])m$/i);
    if (compactMatch) {
      const monthIndex = {
        jan: 0,
        feb: 1,
        mar: 2,
        apr: 3,
        may: 4,
        jun: 5,
        jul: 6,
        aug: 7,
        sep: 8,
        oct: 9,
        nov: 10,
        dec: 11
      }[compactMatch[2].toLowerCase()];

      if (monthIndex !== undefined) {
        const year = Number(compactMatch[3]);
        const fullYear = year < 100 ? 2000 + year : year;
        const meridiem = compactMatch[6].toLowerCase();
        let hour = Number(compactMatch[4]);
        const minute = Number(compactMatch[5] ?? 0);

        if (hour === 12) {
          hour = meridiem === "a" ? 0 : 12;
        } else if (meridiem === "p") {
          hour += 12;
        }

        return new Date(Date.UTC(fullYear, monthIndex, Number(compactMatch[1]), hour, minute, 0, 0)).toISOString();
      }
    }

    const parsed = new Date(text);
    return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
  }

  async function readResponseBody(response) {
    const text = await response.text();
    if (!text) {
      return null;
    }

    try {
      return JSON.parse(text);
    } catch (_error) {
      return text;
    }
  }

  async function saveExample() {
    const sequence = ++state.saveSequence;
    let payload;

    try {
      payload = buildEvalExamplePayload(await getStoredCurrentUser());
    } catch (error) {
      setStatus("save failed", "error");
      setStatePanel(normalizeErrorMessage(error instanceof Error ? error.message : String(error)), "error");
      updateSaveExampleButton();
      return;
    }

    updateSaveExampleButton({ label: "Saving", forceDisabled: true });
    setStatus("saving");

    try {
      const response = await fetch(EVAL_EXAMPLES_ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      const responseBody = await readResponseBody(response);

      if (!response.ok) {
        const message = isPlainObject(responseBody) && responseBody.detail
          ? String(responseBody.detail)
          : `Save failed with HTTP ${response.status}.`;
        throw new Error(message);
      }

      if (sequence !== state.saveSequence) {
        return;
      }

      updateSaveExampleButton({ label: "Saved" });
      setStatus("saved", "success");
      setStatePanel("");

      window.setTimeout(() => {
        if (sequence !== state.saveSequence) {
          return;
        }

        updateSaveExampleButton();
        if (canSaveExample()) {
          setStatus("parsed", "success");
        }
      }, 1600);
    } catch (error) {
      if (sequence !== state.saveSequence) {
        return;
      }

      setStatus("save failed", "error");
      setStatePanel(normalizeErrorMessage(error instanceof Error ? error.message : String(error)), "error");
      updateSaveExampleButton();
    }
  }

  async function refreshParseResult() {
    const sequence = ++state.parseSequence;
    setLoadingState();

    try {
      const result = await parseSourceTab();
      if (sequence !== state.parseSequence) {
        return;
      }

      renderParseResult(result);
    } catch (error) {
      if (sequence !== state.parseSequence) {
        return;
      }

      const result = {
        status: "failed_to_parse_with_appropriate_methodology",
        error: normalizeErrorMessage(error instanceof Error ? error.message : String(error))
      };
      renderParseResult(result);
    }
  }

  refreshButton?.addEventListener("click", () => {
    refreshParseResult();
  });

  saveExampleButton?.addEventListener("click", () => {
    saveExample();
  });

  window.addEventListener("load", () => {
    try {
      setSourceLabel();
      updateUrlState();
      refreshParseResult();
    } catch (error) {
      setStatus("failed", "error");
      setStatePanel(error instanceof Error ? error.message : String(error), "error");
    }
  });
})();
