import http from "node:http";

const host = process.env.CONVO_RELAY_HOST || "127.0.0.1";
const port = Number.parseInt(process.env.CONVO_RELAY_PORT || "8787", 10);
const openAiKey = process.env.OPENAI_API_KEY;
const upstreamUrl = "https://api.openai.com/v1/chat/completions";
const maxBodyBytes = 1024 * 1024;

if (!openAiKey) {
  throw new Error("OPENAI_API_KEY is required before starting the relay.");
}

function isAllowedOrigin(origin) {
  if (!origin) {
    return true;
  }

  return origin.startsWith("chrome-extension://") || origin.startsWith("http://127.0.0.1:");
}

function writeJson(response, statusCode, payload, origin) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  };

  if (origin && isAllowedOrigin(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }

  response.writeHead(statusCode, headers);
  response.end(JSON.stringify(payload));
}

async function readRequestBody(request) {
  const chunks = [];
  let totalBytes = 0;

  for await (const chunk of request) {
    totalBytes += chunk.length;
    if (totalBytes > maxBodyBytes) {
      throw new Error(`Request body exceeds ${maxBodyBytes} bytes.`);
    }

    chunks.push(chunk);
  }

  return Buffer.concat(chunks).toString("utf8");
}

function normalizeRequestBody(requestBodyText) {
  let payload;
  try {
    payload = JSON.parse(requestBodyText);
  } catch (error) {
    throw new Error("Request body must be valid JSON.");
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Request body must be a JSON object.");
  }

  return JSON.stringify({
    ...payload,
    store: false
  });
}

function getNetworkErrorMessage(error) {
  if (!(error instanceof Error)) {
    return String(error);
  }

  const detailParts = [error.message];
  const causeMessage = error.cause && typeof error.cause === "object" && "message" in error.cause
    ? error.cause.message
    : null;

  if (typeof causeMessage === "string" && causeMessage && causeMessage !== error.message) {
    detailParts.push(causeMessage);
  }

  return detailParts.join(": ");
}

async function handleChatCompletion(request, response) {
  const origin = request.headers.origin;
  if (!isAllowedOrigin(origin)) {
    writeJson(response, 403, { error: "Origin is not allowed." }, origin);
    return;
  }

  let requestBody;
  try {
    const requestBodyText = await readRequestBody(request);
    requestBody = normalizeRequestBody(requestBodyText);
  } catch (error) {
    writeJson(response, 400, { error: error instanceof Error ? error.message : String(error) }, origin);
    return;
  }

  let upstreamResponse;
  try {
    upstreamResponse = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${openAiKey}`,
        "Content-Type": "application/json"
      },
      body: requestBody
    });
  } catch (error) {
    const networkErrorMessage = getNetworkErrorMessage(error);
    console.error(`[relay] OpenAI network error: ${networkErrorMessage}`);
    writeJson(response, 502, { error: `Unable to reach OpenAI from the local relay. ${networkErrorMessage}` }, origin);
    return;
  }

  const text = await upstreamResponse.text();
  const headers = {
    "Content-Type": upstreamResponse.headers.get("content-type") || "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  };

  if (origin && isAllowedOrigin(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
    headers["Vary"] = "Origin";
  }

  response.writeHead(upstreamResponse.status, headers);
  response.end(text);
}

const server = http.createServer(async (request, response) => {
  const origin = request.headers.origin;

  if (request.method === "OPTIONS") {
    if (!isAllowedOrigin(origin)) {
      response.writeHead(403);
      response.end();
      return;
    }

    response.writeHead(204, {
      "Access-Control-Allow-Origin": origin || `http://${host}:${port}`,
      "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "600",
      "Vary": "Origin"
    });
    response.end();
    return;
  }

  if (request.method === "GET" && request.url === "/health") {
    writeJson(response, 200, {
      ok: true,
      relay: "convo-maker",
      upstream: "openai-chat-completions"
    }, origin);
    return;
  }

  if (request.method === "POST" && request.url === "/v1/chat/completions") {
    await handleChatCompletion(request, response);
    return;
  }

  writeJson(response, 404, { error: "Not found." }, origin);
});

server.listen(port, host, () => {
  console.log(`Convo Maker relay listening on http://${host}:${port}`);
  console.log("Health check: /health");
});
