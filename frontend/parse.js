(() => {
  const LINKEDIN_MESSAGING_PARSER_ID = "linkedin-messaging";
  const SELF_SENDER_NAME = "Quentin Glangetas";
  const SELF_RATING_LABELS = ["very poor", "poor", "neutral", "good", "very good"];
  const OTHER_RATING_LABELS = ["unhelpful", "confused", "neutral", "good", "very good"];
  const PARSE_RETRY_DELAY_MS = 250;
  const PARSE_RETRY_TIMEOUT_MS = 3500;
  const PARSER_FILES = [
    "frontend/content/parsing/runtime.js",
    "frontend/content/parsing/helpers.js",
    "frontend/content/parsing/parsers/linkedin-messaging.js"
  ];

  const refreshButton = document.getElementById("refresh-button");
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
    parseSequence: 0
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
        const wait = (durationMs) => new Promise((resolve) => {
          globalThis.setTimeout(resolve, durationMs);
        });

        const isRecoverableLinkedInMessagingFailure = (parseResult) => {
          if (parseResult?.status !== "failed_to_parse_with_appropriate_methodology") {
            return false;
          }

          if (parseResult?.parserId !== "linkedin-messaging") {
            return false;
          }

          return /message list was not found|no linkedin messages were extracted/i.test(parseResult?.error ?? "");
        };

        const nudgePageLifecycle = () => {
          const events = [
            () => globalThis.dispatchEvent(new Event("focus")),
            () => globalThis.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: false })),
            () => globalThis.dispatchEvent(new Event("online")),
            () => document.dispatchEvent(new Event("visibilitychange"))
          ];

          for (const dispatchEvent of events) {
            try {
              dispatchEvent();
            } catch (_error) {
              // Best-effort only; parsing can continue without lifecycle nudges.
            }
          }
        };

        const parse = () => {
          if (parserIdOverride && globalThis.ConverseParsing.parseDocumentWithParserId) {
            return globalThis.ConverseParsing.parseDocumentWithParserId(
              parserIdOverride,
              globalThis.location?.href ?? "",
              document
            );
          }

          return globalThis.ConverseParsing.parseCurrentPage();
        };

        if (!globalThis.ConverseParsing?.parseCurrentPage) {
          return {
            status: "failed_to_parse_with_appropriate_methodology",
            error: "Parser runtime is unavailable on the current page."
          };
        }

        let result = parse();
        if (!isRecoverableLinkedInMessagingFailure(result)) {
          return result;
        }

        nudgePageLifecycle();

        const deadline = Date.now() + retryTimeoutMs;
        while (Date.now() < deadline) {
          await wait(retryDelayMs);
          result = parse();

          if (!isRecoverableLinkedInMessagingFailure(result)) {
            return result;
          }

          nudgePageLifecycle();
        }

        return result;
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

  function createMessageControls(item, index, selection) {
    const controls = document.createElement("aside");
    controls.className = "message-controls";
    controls.append(
      createCategoryControl(item, index, selection),
      createRatingControl(item, index, selection)
    );
    return controls;
  }

  function renderMessageItem(item, index) {
    const messageRecord = isPlainObject(item) ? item : { message: String(item ?? "") };
    const selection = {
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

    row.append(
      main,
      createMessageControls(messageRecord, index, selection)
    );

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
      return;
    }

    if (normalized.parserId !== LINKEDIN_MESSAGING_PARSER_ID) {
      setStatus("wrong parser", "error");
      setStatePanel("This lookup window only supports LinkedIn message threads.", "error");
      parseOutput.append(renderRawResult(normalized));
      return;
    }

    const output = isPlainObject(normalized.output) ? normalized.output : null;
    if (!Array.isArray(output?.messages)) {
      setStatus("no messages", "error");
      setStatePanel("LinkedIn parsing succeeded, but no message array was returned.", "error");
      parseOutput.append(renderRawResult(normalized));
      return;
    }

    setStatus("parsed", "success");
    setStatePanel("");
    parseOutput.append(renderMessageArray(output.messages));
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
