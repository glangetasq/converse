(() => {
  const existingNamespace = globalThis.ConverseParsing ?? {};
  const parsers = existingNamespace.parsers ?? [];

  const ParseStatus = Object.freeze({
    SUCCESS: "success",
    UNSUPPORTED_URL: "failed_to_find_appropriate_parsing_methodology",
    PARSER_FAILED: "failed_to_parse_with_appropriate_methodology"
  });

  function normalizePathname(pathname) {
    if (!pathname) {
      return "/";
    }

    if (pathname.length > 1 && pathname.endsWith("/")) {
      return pathname.slice(0, -1);
    }

    return pathname;
  }

  function pathnameMatchesPrefix(pathname, prefixPathname) {
    const normalizedPathname = normalizePathname(pathname);
    const normalizedPrefix = normalizePathname(prefixPathname);

    return normalizedPathname === normalizedPrefix
      || normalizedPathname.startsWith(`${normalizedPrefix}/`);
  }

  function createUrlPrefixMatcher(urlPrefixes) {
    const normalizedPrefixes = (Array.isArray(urlPrefixes) ? urlPrefixes : []).map((urlPrefix) => new URL(urlPrefix));

    return (url) => {
      const parsedUrl = new URL(url);

      return normalizedPrefixes.some((urlPrefix) => (
        parsedUrl.protocol === urlPrefix.protocol
        && parsedUrl.hostname === urlPrefix.hostname
        && pathnameMatchesPrefix(parsedUrl.pathname, urlPrefix.pathname)
      ));
    };
  }

  function registerParser(parser) {
    if (!parser || typeof parser.id !== "string" || typeof parser.parse !== "function") {
      throw new Error("Parser registration requires id and parse(context).");
    }

    const hasMatcherFunction = typeof parser.matches === "function";
    const hasUrlPrefixes = Array.isArray(parser.urlPrefixes) && parser.urlPrefixes.length > 0;
    const isManualOnly = parser.manualOnly === true;

    if (!isManualOnly && !hasMatcherFunction && !hasUrlPrefixes) {
      throw new Error("Parser registration requires matches(url) or urlPrefixes.");
    }

    const normalizedParser = {
      ...parser,
      matches: hasMatcherFunction
        ? parser.matches
        : (isManualOnly ? () => false : createUrlPrefixMatcher(parser.urlPrefixes))
    };

    const existingIndex = parsers.findIndex((candidate) => candidate.id === parser.id);
    if (existingIndex >= 0) {
      parsers.splice(existingIndex, 1, normalizedParser);
      return;
    }

    parsers.push(normalizedParser);
  }

  function findParserForUrl(url) {
    return parsers.find((parser) => {
      try {
        return parser.matches(url);
      } catch (error) {
        console.warn("Parser URL matcher failed.", parser.id, error);
        return false;
      }
    }) ?? null;
  }

  function findParserById(parserId) {
    if (!parserId) {
      return null;
    }

    return parsers.find((parser) => parser.id === parserId) ?? null;
  }

  function runParser(parser, url, doc = document) {
    if (!parser) {
      return {
        status: ParseStatus.UNSUPPORTED_URL,
        url
      };
    }

    try {
      const output = parser.parse({ document: doc, url });
      return {
        status: ParseStatus.SUCCESS,
        parserId: parser.id,
        url,
        output
      };
    } catch (error) {
      return {
        status: ParseStatus.PARSER_FAILED,
        parserId: parser.id,
        url,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  function parseDocumentForUrl(url, doc = document) {
    return runParser(findParserForUrl(url), url, doc);
  }

  function parseDocumentWithParserId(parserId, url, doc = document) {
    const parser = findParserById(parserId);
    if (!parser) {
      return {
        status: ParseStatus.UNSUPPORTED_URL,
        parserId,
        url,
        error: `Unknown parser "${parserId}".`
      };
    }

    return runParser(parser, url, doc);
  }

  function parseCurrentPage(doc = document) {
    return parseDocumentForUrl(globalThis.location?.href ?? "", doc);
  }

  globalThis.ConverseParsing = {
    ...existingNamespace,
    ParseStatus,
    parsers,
    registerParser,
    createUrlPrefixMatcher,
    findParserForUrl,
    findParserById,
    parseDocumentForUrl,
    parseDocumentWithParserId,
    parseCurrentPage
  };
})();
