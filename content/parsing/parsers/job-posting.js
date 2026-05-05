(() => {
  const namespace = globalThis.ConverseParsing;
  const helpers = namespace?.helpers;

  if (!namespace || !helpers) {
    throw new Error("Job posting parser loaded before runtime helpers.");
  }

  const SITE_CONFIGS = Object.freeze({
    linkedin: Object.freeze({
      titleSelectors: [
        ".job-details-jobs-unified-top-card__job-title",
        ".jobs-unified-top-card__job-title",
        ".top-card-layout__title",
        "main h1"
      ],
      companySelectors: [
        ".job-details-jobs-unified-top-card__company-name",
        ".jobs-unified-top-card__company-name",
        ".topcard__org-name-link",
        ".topcard__flavor a"
      ],
      locationSelectors: [
        ".job-details-jobs-unified-top-card__primary-description-container",
        ".jobs-unified-top-card__primary-description-container",
        ".topcard__flavor--bullet"
      ],
      contentSelectors: [
        ".jobs-description__content",
        ".jobs-box__html-content",
        ".jobs-description-content__text",
        ".jobs-description__container"
      ]
    }),
    indeed: Object.freeze({
      titleSelectors: [
        "[data-testid='jobsearch-JobInfoHeader-title']",
        ".jobsearch-JobInfoHeader-title",
        "main h1"
      ],
      companySelectors: [
        "[data-testid='inlineHeader-companyName']",
        ".jobsearch-InlineCompanyRating-companyHeader",
        "[data-testid='company-name']"
      ],
      locationSelectors: [
        "[data-testid='job-location']",
        "[data-testid='inlineHeader-companyLocation']",
        ".jobsearch-JobInfoHeader-subtitle div"
      ],
      contentSelectors: [
        "#jobDescriptionText",
        "[data-testid='jobsearch-JobComponent-description']",
        "#jobDescription"
      ]
    }),
    welcometothejungle: Object.freeze({
      titleSelectors: [
        "main h1",
        "[data-testid='job-title']"
      ],
      companySelectors: [
        "[data-testid='company-name']",
        "a[href*='/companies/']"
      ],
      locationSelectors: [
        "[data-testid='job-location']",
        "[href*='maps']"
      ],
      contentSelectors: [
        "[data-testid='job-description']",
        "main article",
        "main"
      ]
    }),
    workday: Object.freeze({
      titleSelectors: [
        "[data-automation-id='jobPostingHeader'] h1",
        "[data-automation-id='jobPostingHeader']"
      ],
      companySelectors: [
        "[data-automation-id='company-name']",
        "[data-automation-id='jobPostingCompany']",
        "header img[alt]"
      ],
      locationSelectors: [
        "[data-automation-id='locations']",
        "[data-automation-id='primaryLocation']"
      ],
      contentSelectors: [
        "[data-automation-id='jobPostingDescription']",
        "[data-automation-id='jobDescription']",
        "[data-automation-id='postingDescription']"
      ]
    }),
    greenhouse: Object.freeze({
      titleSelectors: [
        "#header h1",
        ".app-title",
        ".job-post-header h1",
        "main h1"
      ],
      companySelectors: [
        "#header .company-name",
        ".company-name"
      ],
      locationSelectors: [
        "#header .location",
        ".location"
      ],
      contentSelectors: [
        "#content",
        "#job-details",
        ".job-post",
        "main article"
      ]
    })
  });

  function normalizeText(value) {
    return String(value ?? "")
      .replace(/\u00a0/g, " ")
      .replace(/\r/g, "")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  function uniqueTexts(values) {
    const seen = new Set();

    return values.filter((value) => {
      const text = normalizeText(value);
      if (!text || seen.has(text)) {
        return false;
      }

      seen.add(text);
      return true;
    }).map((value) => normalizeText(value));
  }

  function isVisible(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    const style = globalThis.getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
      return false;
    }

    const rect = element.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function isNoiseElement(element) {
    if (!(element instanceof Element)) {
      return true;
    }

    const tagName = element.tagName.toLowerCase();
    if (["script", "style", "noscript", "svg", "path", "footer", "nav", "aside", "form"].includes(tagName)) {
      return true;
    }

    const descriptor = `${element.id || ""} ${element.className || ""}`.toLowerCase();
    return /\b(?:nav|footer|header|cookie|consent|banner|modal|drawer|popover|tooltip|share|social|apply|signin|login|register|nearby|similar|related|recommended|salary-guide)\b/.test(descriptor);
  }

  function getText(element) {
    return normalizeText(helpers.getNormalizedInnerText(element));
  }

  function getTextFromSelectorList(document, selectors) {
    for (const selector of selectors) {
      const match = Array.from(document.querySelectorAll(selector)).find((element) => isVisible(element) && !isNoiseElement(element) && getText(element));
      if (match) {
        return getText(match);
      }
    }

    return null;
  }

  function getElementsFromSelectorList(document, selectors) {
    return selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)))
      .filter((element, index, array) => array.indexOf(element) === index)
      .filter((element) => isVisible(element) && !isNoiseElement(element));
  }

  function getSelectionText() {
    const selection = globalThis.getSelection?.();
    if (!selection || selection.isCollapsed) {
      return null;
    }

    const text = normalizeText(selection.toString());
    return text.length >= 80 ? text : null;
  }

  function getHostname(url) {
    try {
      return new URL(url).hostname.toLowerCase();
    } catch (_error) {
      return "";
    }
  }

  function detectSite(url) {
    const hostname = getHostname(url);

    if (hostname.includes("linkedin.")) {
      return "linkedin";
    }

    if (hostname.includes("indeed.")) {
      return "indeed";
    }

    if (hostname.includes("welcometothejungle.")) {
      return "welcometothejungle";
    }

    if (hostname.includes("greenhouse.")) {
      return "greenhouse";
    }

    if (hostname.includes("myworkdayjobs.com") || hostname.includes("workday.")) {
      return "workday";
    }

    return "generic";
  }

  function collectJsonLdObjects(value, results = []) {
    if (Array.isArray(value)) {
      value.forEach((entry) => collectJsonLdObjects(entry, results));
      return results;
    }

    if (!value || typeof value !== "object") {
      return results;
    }

    results.push(value);

    if (Array.isArray(value["@graph"])) {
      value["@graph"].forEach((entry) => collectJsonLdObjects(entry, results));
    }

    Object.values(value).forEach((entry) => {
      if (entry && typeof entry === "object" && entry !== value["@graph"]) {
        collectJsonLdObjects(entry, results);
      }
    });

    return results;
  }

  function parseJsonLdJobPosting(document) {
    const scripts = Array.from(document.querySelectorAll("script[type='application/ld+json']"));

    for (const script of scripts) {
      try {
        const raw = JSON.parse(script.textContent || "null");
        const objects = collectJsonLdObjects(raw);
        const jobPosting = objects.find((entry) => {
          const typeValue = entry?.["@type"];
          if (Array.isArray(typeValue)) {
            return typeValue.some((candidate) => String(candidate).toLowerCase() === "jobposting");
          }

          return String(typeValue || "").toLowerCase() === "jobposting";
        });

        if (!jobPosting) {
          continue;
        }

        return {
          title: normalizeText(jobPosting.title || ""),
          company: normalizeText(jobPosting.hiringOrganization?.name || ""),
          location: normalizeText(
            jobPosting.jobLocation?.address?.addressLocality
            || jobPosting.jobLocation?.address?.addressRegion
            || jobPosting.jobLocation?.address?.addressCountry
            || ""
          ),
          description: normalizeHtmlText(jobPosting.description || ""),
          signals: ["jsonld-jobposting"]
        };
      } catch (_error) {
        continue;
      }
    }

    return null;
  }

  function normalizeHtmlText(value) {
    const container = document.createElement("div");
    container.innerHTML = String(value ?? "");
    return normalizeText(container.textContent || "");
  }

  function splitIntoBlocks(text) {
    const pieces = normalizeText(text)
      .split(/\n{2,}/)
      .map((value) => value.split(/\n(?=[A-Z0-9][^\n]{0,80}$)/g))
      .flat()
      .map((value) => normalizeText(value))
      .filter(Boolean);

    const merged = [];

    for (const piece of pieces) {
      if (piece.length < 80 && merged.length > 0) {
        merged[merged.length - 1] = `${merged[merged.length - 1]}\n${piece}`;
        continue;
      }

      merged.push(piece);
    }

    return uniqueTexts(merged)
      .filter((value) => value.length >= 120)
      .slice(0, 8);
  }

  function getKeywordScore(text) {
    const patterns = [
      /\b(?:job description|about the role|about the job|responsibilities|what you(?:'ll| will) do|what we(?:'re| are) looking for|requirements|qualifications|about us|about the team|mission|your profile|you will|we are looking for)\b/gi,
      /\b(?:experience|skills|team|product|customers?|stakeholders?|build|own|develop|deliver|strategy|roadmap)\b/gi
    ];

    return patterns.reduce((total, pattern, index) => {
      const matches = text.match(pattern) ?? [];
      const weight = index === 0 ? 4 : 1;
      return total + matches.length * weight;
    }, 0);
  }

  function getLinkDensityScore(element, textLength) {
    const linkTextLength = Array.from(element.querySelectorAll("a"))
      .map((link) => getText(link).length)
      .reduce((sum, length) => sum + length, 0);

    return textLength > 0 ? linkTextLength / textLength : 0;
  }

  function scoreCandidate(element) {
    const text = getText(element);
    if (text.length < 200) {
      return null;
    }

    const descriptor = `${element.id || ""} ${element.className || ""}`.toLowerCase();
    const paragraphCount = element.querySelectorAll("p, li").length;
    const headingCount = element.querySelectorAll("h1, h2, h3, h4").length;
    const linkDensity = getLinkDensityScore(element, text.length);

    let score = 0;
    score += Math.min(text.length, 5000) / 250;
    score += Math.min(paragraphCount, 18) * 0.7;
    score += Math.min(headingCount, 6) * 1.1;
    score += getKeywordScore(text);

    if (/\b(?:job|role|career|position|posting|description|detail|responsibilit|qualif|mission|about)\b/.test(descriptor)) {
      score += 8;
    }

    if (/\b(?:related|similar|recommended|share|social|benefits-only|cookie|footer|nav|header)\b/.test(descriptor)) {
      score -= 12;
    }

    if (linkDensity > 0.33) {
      score -= 10;
    }

    if (element.matches("main, article, section")) {
      score += 4;
    }

    return {
      element,
      text,
      score
    };
  }

  function collectGenericCandidates(document) {
    const selector = [
      "[role='main']",
      "main",
      "article",
      "section",
      "div"
    ].join(", ");

    return Array.from(document.querySelectorAll(selector))
      .filter((element) => isVisible(element) && !isNoiseElement(element))
      .map((element) => scoreCandidate(element))
      .filter(Boolean)
      .sort((left, right) => right.score - left.score);
  }

  function removeContainedBlocks(blocks) {
    return blocks.filter((block, index) => !blocks.some((candidate, candidateIndex) => (
      candidateIndex !== index
      && candidate.length > block.length
      && candidate.includes(block)
    )));
  }

  function deriveCompanyFromTitle(value) {
    const text = normalizeText(value);
    if (!text) {
      return null;
    }

    const parts = text.split(/\s+[·|-]\s+/);
    return parts.length > 1 ? parts.at(-1) ?? null : null;
  }

  function buildOutput({ document, url, site, jsonLd, siteRoots }) {
    const siteConfig = SITE_CONFIGS[site] ?? null;
    const selectedText = getSelectionText();
    const genericCandidates = collectGenericCandidates(document);
    const primarySiteRoot = siteRoots[0] ?? null;
    const genericPrimary = genericCandidates[0] ?? null;
    const primaryText = normalizeText(
      selectedText
      || getText(primarySiteRoot)
      || jsonLd?.description
      || genericPrimary?.text
      || ""
    );

    const siteBlocks = siteRoots.flatMap((element) => splitIntoBlocks(getText(element))).slice(0, 6);
    const genericBlocks = genericCandidates.slice(0, 4).flatMap((candidate) => splitIntoBlocks(candidate.text)).slice(0, 6);
    const supportingTextBlocks = removeContainedBlocks(uniqueTexts([
      ...siteBlocks,
      ...genericBlocks
    ])).filter((block) => block !== primaryText).slice(0, 8);

    const rawText = normalizeText(uniqueTexts([
      selectedText,
      primaryText,
      ...supportingTextBlocks
    ]).join("\n\n"));

    if (rawText.length < 180) {
      throw new Error("Unable to isolate enough job description text from the current page.");
    }

    const signals = uniqueTexts([
      ...(jsonLd?.signals ?? []),
      site !== "generic" ? `site:${site}` : "",
      primarySiteRoot ? "site-specific-root" : "",
      genericPrimary ? "generic-root" : "",
      selectedText ? "user-selection" : ""
    ]);

    const title = normalizeText(
      jsonLd?.title
      || (siteConfig ? getTextFromSelectorList(document, siteConfig.titleSelectors) : "")
      || getTextFromSelectorList(document, ["main h1", "h1"])
      || document.title
    ) || null;

    const company = normalizeText(
      jsonLd?.company
      || (siteConfig ? getTextFromSelectorList(document, siteConfig.companySelectors) : "")
      || deriveCompanyFromTitle(document.title)
      || ""
    ) || null;

    const location = normalizeText(
      jsonLd?.location
      || (siteConfig ? getTextFromSelectorList(document, siteConfig.locationSelectors) : "")
      || ""
    ) || null;

    const confidence = Math.max(
      0.2,
      Math.min(
        0.98,
        (
          (jsonLd ? 0.28 : 0)
          + (primarySiteRoot ? 0.26 : 0)
          + (genericPrimary ? 0.2 : 0)
          + (selectedText ? 0.08 : 0)
          + Math.min(rawText.length / 4000, 0.16)
        )
      )
    );

    return {
      source_type: "job_posting",
      site,
      url,
      page_title: normalizeText(document.title || "") || null,
      title,
      company,
      location,
      selected_text: selectedText,
      primary_text: primaryText,
      supporting_text_blocks: supportingTextBlocks,
      raw_text: rawText,
      signals,
      confidence: Number(confidence.toFixed(2))
    };
  }

  function parseJobPosting({ document, url }) {
    const site = detectSite(url);
    const siteConfig = SITE_CONFIGS[site] ?? null;
    const jsonLd = parseJsonLdJobPosting(document);
    const siteRoots = siteConfig
      ? getElementsFromSelectorList(document, siteConfig.contentSelectors)
      : [];

    return buildOutput({
      document,
      url,
      site,
      jsonLd,
      siteRoots
    });
  }

  namespace.registerParser({
    id: "job-posting",
    manualOnly: true,
    parse: parseJobPosting
  });
})();
