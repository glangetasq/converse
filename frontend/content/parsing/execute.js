(() => {
  const namespace = globalThis.ConverseParsing;

  if (!namespace) {
    throw new Error("Parser execution helper loaded before parser runtime.");
  }

  function wait(durationMs) {
    return new Promise((resolve) => {
      globalThis.setTimeout(resolve, durationMs);
    });
  }

  function isRecoverableLinkedInMessagingFailure(parseResult) {
    if (parseResult?.status !== namespace.ParseStatus.PARSER_FAILED) {
      return false;
    }

    if (parseResult?.parserId !== "linkedin-messaging") {
      return false;
    }

    return /message list was not found|no linkedin messages were extracted/i.test(parseResult?.error ?? "");
  }

  function nudgePageLifecycle() {
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
  }

  function parse(parserIdOverride) {
    if (parserIdOverride && namespace.parseDocumentWithParserId) {
      return namespace.parseDocumentWithParserId(
        parserIdOverride,
        globalThis.location?.href ?? "",
        document
      );
    }

    return namespace.parseCurrentPage();
  }

  async function parseCurrentPageWithRetry(parserIdOverride, retryDelayMs, retryTimeoutMs) {
    if (!namespace.parseCurrentPage) {
      return {
        status: namespace.ParseStatus.PARSER_FAILED,
        error: "Parser runtime is unavailable on the current page."
      };
    }

    let result = parse(parserIdOverride);
    if (!isRecoverableLinkedInMessagingFailure(result)) {
      return result;
    }

    nudgePageLifecycle();

    const deadline = Date.now() + retryTimeoutMs;
    while (Date.now() < deadline) {
      await wait(retryDelayMs);
      result = parse(parserIdOverride);

      if (!isRecoverableLinkedInMessagingFailure(result)) {
        return result;
      }

      nudgePageLifecycle();
    }

    return result;
  }

  globalThis.ConverseParsing = {
    ...namespace,
    parseCurrentPageWithRetry
  };
})();
