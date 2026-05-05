(() => {
  const namespace = globalThis.ConverseParsing ?? {};

  function getNormalizedInnerText(node) {
    if (!node) {
      return "";
    }

    return node.innerText.replace(/\u00a0/g, " ").trim();
  }

  function getFirstMatchText(root, selector) {
    return getNormalizedInnerText(root?.querySelector(selector) ?? null);
  }

  function appendMessageLine(baseText, nextText) {
    if (!baseText) {
      return nextText;
    }

    if (!nextText) {
      return baseText;
    }

    return `${baseText}\n${nextText}`;
  }

  function isLikelyPresenceText(value) {
    return /(?:^|\b)(mobile|available|reachable)\b/i.test(value) || /\bago$/i.test(value);
  }

  namespace.helpers = {
    getNormalizedInnerText,
    getFirstMatchText,
    appendMessageLine,
    isLikelyPresenceText
  };

  globalThis.ConverseParsing = namespace;
})();
