(() => {
  function isVisible(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden") {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isEligibleInput(element) {
    if (!(element instanceof HTMLElement) || !isVisible(element)) {
      return false;
    }

    if (element instanceof HTMLTextAreaElement) {
      return !element.disabled && !element.readOnly;
    }

    if (element instanceof HTMLInputElement) {
      return !element.disabled && !element.readOnly && (!element.type || element.type === "text");
    }

    return element.isContentEditable;
  }

  function setInputValue(element, value) {
    const prototype = element instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");

    if (descriptor?.set) {
      descriptor.set.call(element, value);
      return;
    }

    element.value = value;
  }

  function setContentEditableValue(element, value) {
    element.focus();

    const selection = window.getSelection();
    if (selection) {
      const range = document.createRange();
      range.selectNodeContents(element);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    let inserted = false;

    if (typeof document.execCommand === "function") {
      try {
        document.execCommand("selectAll", false, null);
        inserted = document.execCommand("insertText", false, value);
      } catch (_error) {
        inserted = false;
      }
    }

    if (!inserted) {
      const lines = value.split("\n");
      element.replaceChildren();

      lines.forEach((line, index) => {
        if (index > 0) {
          element.append(document.createElement("br"));
        }

        element.append(document.createTextNode(line));
      });
    }
  }

  function dispatchEditableEvents(element, value) {
    element.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: value
    }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getTargetElement() {
    const activeElement = document.activeElement;
    if (isEligibleInput(activeElement)) {
      return activeElement;
    }

    const selectors = [
      ".msg-form__contenteditable[contenteditable='true']",
      ".msg-form__contenteditable",
      "[role='textbox'][contenteditable='true']",
      "textarea:not([readonly]):not([disabled])",
      "input[type='text']:not([readonly]):not([disabled])",
      "[contenteditable='true']"
    ];

    for (const selector of selectors) {
      const match = Array.from(document.querySelectorAll(selector)).find(isEligibleInput);
      if (match) {
        return match;
      }
    }

    return null;
  }

  function injectSuggestion(suggestionText) {
    if (typeof suggestionText !== "string" || !suggestionText.trim()) {
      return {
        ok: false,
        error: "Suggestion is empty."
      };
    }

    const target = getTargetElement();
    if (!target) {
      return {
        ok: false,
        error: "No editable message field was found on the page."
      };
    }

    target.focus();

    if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
      setInputValue(target, suggestionText);
      target.setSelectionRange?.(suggestionText.length, suggestionText.length);
    } else {
      setContentEditableValue(target, suggestionText);
    }

    dispatchEditableEvents(target, suggestionText);
    target.scrollIntoView({ block: "nearest" });

    return {
      ok: true
    };
  }

  globalThis.ConverseSuggestionInjection = Object.freeze({
    injectSuggestion
  });
})();
