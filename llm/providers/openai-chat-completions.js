(() => {
  const PROVIDER_ID = "openai-chat-completions";

  if (!globalThis.ConverseLlmProviders) {
    globalThis.ConverseLlmProviders = {};
  }

  function buildMessages(request) {
    return [
      {
        role: "system",
        content: [
          "You write tailored communication drafts from the provided prompt and context.",
          "Return valid JSON only.",
          "Do not include markdown, numbering, commentary, or labels."
        ].join(" ")
      },
      {
        role: "user",
        content: [
          request.promptText,
          "",
          `Return a JSON object with a "suggestions" array containing exactly ${request.suggestionCount} distinct suggestions.`,
          "Each suggestion must contain only the draft text, with no labels or commentary."
        ].join("\n")
      }
    ];
  }

  function extractMessageContent(payload) {
    return payload?.choices?.[0]?.message?.content ?? "";
  }

  function extractJsonObject(rawContent) {
    const trimmed = rawContent.trim();
    if (!trimmed) {
      throw new Error("The provider returned an empty response.");
    }

    try {
      return JSON.parse(trimmed);
    } catch (error) {
      const objectMatch = trimmed.match(/\{[\s\S]*\}/);
      if (objectMatch) {
        return JSON.parse(objectMatch[0]);
      }

      throw error;
    }
  }

  function parseSuggestions(rawContent, suggestionCount) {
    const parsed = extractJsonObject(rawContent);
    const suggestions = Array.isArray(parsed?.suggestions)
      ? parsed.suggestions
        .filter((value) => typeof value === "string")
        .map((value) => value.trim())
        .filter(Boolean)
      : [];

    if (suggestions.length < suggestionCount) {
      throw new Error("The provider response did not include the expected suggestions array.");
    }

    return suggestions.slice(0, suggestionCount);
  }

  function getEndpoint(settings) {
    return new URL(settings.path, `${settings.baseUrl}/`).toString();
  }

  function buildRequestBody(request, settings) {
    return {
      model: settings.model,
      temperature: settings.temperature,
      store: false,
      response_format: { type: "json_object" },
      messages: buildMessages(request)
    };
  }

  async function readErrorMessage(response, responseText) {
    if (!responseText) {
      return `${response.status} ${response.statusText}`.trim();
    }

    try {
      const parsed = JSON.parse(responseText);
      return parsed?.error?.message || responseText;
    } catch (error) {
      return responseText;
    }
  }

  async function generate(request, settings) {
    const endpoint = getEndpoint(settings);
    const requestBody = buildRequestBody(request, settings);

    let response;
    try {
      response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(requestBody)
      });
    } catch (error) {
      throw new Error("Relay request failed: Unable to reach the configured relay URL.");
    }

    const responseText = await response.text();
    if (!response.ok) {
      const message = await readErrorMessage(response, responseText);

      if (response.status === 504 || /timeout|timed out/i.test(message)) {
        throw new Error(`LLM API timeout: ${message}`);
      }

      if (response.status === 502 || response.status === 503) {
        throw new Error(`LLM API request failed: ${message}`);
      }

      throw new Error(`LLM request failed: ${message}`);
    }

    let payload;
    try {
      payload = JSON.parse(responseText);
    } catch (error) {
      throw new Error("The provider response was not valid JSON.");
    }

    const rawContent = extractMessageContent(payload);
    if (typeof rawContent !== "string") {
      throw new Error("The provider response did not include assistant text.");
    }

    return {
      endpoint,
      model: payload?.model ?? settings.model,
      provider: PROVIDER_ID,
      rawContent,
      suggestions: parseSuggestions(rawContent, request.suggestionCount),
      usage: payload?.usage ?? null
    };
  }

  globalThis.ConverseLlmProviders[PROVIDER_ID] = Object.freeze({
    generate,
    id: PROVIDER_ID
  });
})();
