(() => {
  const namespace = globalThis.ConverseParsing;
  const helpers = namespace?.helpers;

  if (!namespace || !helpers) {
    throw new Error("LinkedIn profile parser loaded before runtime helpers.");
  }

  function normalizePathname(pathname) {
    if (!pathname) {
      return "/";
    }

    if (pathname.length > 1 && pathname.endsWith("/")) {
      return pathname.slice(0, -1);
    }

    return pathname;
  }

  function isProfilePathname(pathname) {
    return /^\/in\/[^/]+$/i.test(normalizePathname(pathname));
  }

  function getProfilePathname(url) {
    return normalizePathname(new URL(url).pathname);
  }

  function isConnectionDegreeText(text) {
    return /^·?\s*(?:1st|2nd|3rd|\d+(?:st|nd|rd|th))$/i.test(text);
  }

  function isActionText(text) {
    return /^(?:contact info|message|more|follow|connect|open to|see more|see less|show all .*?)$/i.test(text);
  }

  function isChromeText(text) {
    // Global LinkedIn navigation chrome (e.g. the notification bell) renders its own
    // headings outside the profile <main>, so guard against them leaking into fields.
    return /^\d*\s*notifications?$/i.test(text)
      || /^(?:he|she|they)\/(?:him|her|them)$/i.test(text);
  }

  function isMetricText(text) {
    return /\bfollowers?\b/i.test(text)
      || /\bconnections?\b/i.test(text)
      || /\bmutual connections?\b/i.test(text);
  }

  function isNoiseText(text) {
    return !text
      || text === "·"
      || isConnectionDegreeText(text)
      || isActionText(text)
      || isChromeText(text)
      || isMetricText(text)
      || /^https?:\/\//i.test(text)
      || helpers.isLikelyPresenceText(text);
  }

  function looksLikeLocation(text) {
    return !isNoiseText(text)
      && text.includes(",")
      && !/\b(?:advisor|consultant|founder|investor|writer|editor|contributor|operator|builder|speaker)\b/i.test(text);
  }

  function doesAnchorMatchProfile(anchor, profilePathname) {
    const href = anchor?.getAttribute("href");
    if (!href) {
      return false;
    }

    try {
      return normalizePathname(new URL(href, globalThis.location.href).pathname) === profilePathname;
    } catch (_error) {
      return false;
    }
  }

  function findNameElement(document, profilePathname) {
    const preferredCandidates = Array.from(
      document.querySelectorAll("a[href] h1, a[href] h2, a[href] h3")
    );

    const preferredMatch = preferredCandidates.find((candidate) => {
      const text = helpers.getNormalizedInnerText(candidate);
      return text && !isNoiseText(text) && doesAnchorMatchProfile(candidate.closest("a[href]"), profilePathname);
    });

    if (preferredMatch) {
      return preferredMatch;
    }

    // querySelectorAll returns matches in document order, not selector order, so scope to
    // <main> first. Otherwise global nav headings (e.g. the "0 notifications" bell, which
    // renders as an <h2> before <main>) win and the real name leaks into other fields.
    const searchRoots = [document.querySelector("main"), document].filter(Boolean);

    for (const root of searchRoots) {
      const match = Array.from(root.querySelectorAll("h1, h2, h3")).find((candidate) => {
        const text = helpers.getNormalizedInnerText(candidate);
        return text && !isNoiseText(text);
      });

      if (match) {
        return match;
      }
    }

    return null;
  }

  function findHeaderRoot(nameElement) {
    let current = nameElement?.parentElement ?? null;

    while (current) {
      if (current.querySelector("a[href*='/overlay/contact-info/']")) {
        return current;
      }

      current = current.parentElement;
    }

    return nameElement?.parentElement ?? null;
  }

  function getParagraphsAfter(root, nameElement) {
    if (!root || !nameElement) {
      return [];
    }

    return Array.from(root.querySelectorAll("p")).filter((paragraph) => (
      Boolean(nameElement.compareDocumentPosition(paragraph) & Node.DOCUMENT_POSITION_FOLLOWING)
    ));
  }

  function extractHeadline(headerRoot, nameElement, location) {
    const paragraphs = getParagraphsAfter(headerRoot, nameElement);

    for (const paragraph of paragraphs) {
      const text = helpers.getNormalizedInnerText(paragraph);
      if (isNoiseText(text) || text === location || looksLikeLocation(text)) {
        continue;
      }

      return text;
    }

    return null;
  }

  function extractLocation(headerRoot, nameElement) {
    const contactInfoLink = headerRoot?.querySelector("a[href*='/overlay/contact-info/']");
    const contactInfoContainer = contactInfoLink?.closest("p") ?? null;

    let sibling = contactInfoContainer?.previousElementSibling ?? null;
    while (sibling) {
      const text = helpers.getNormalizedInnerText(sibling);
      if (!isNoiseText(text)) {
        return text;
      }

      sibling = sibling.previousElementSibling;
    }

    const locationCandidates = getParagraphsAfter(headerRoot, nameElement)
      .map((paragraph) => helpers.getNormalizedInnerText(paragraph))
      .filter((text) => looksLikeLocation(text));

    return locationCandidates.at(-1) ?? null;
  }

  function findAboutHeading(document) {
    return Array.from(document.querySelectorAll("h1, h2, h3, h4, span, div, p")).find((element) => (
      helpers.getNormalizedInnerText(element) === "About"
    )) ?? null;
  }

  function extractAbout(document) {
    const aboutHeading = findAboutHeading(document);
    if (!aboutHeading) {
      return null;
    }

    const section = aboutHeading.closest("section") ?? aboutHeading.parentElement;
    if (!section) {
      return null;
    }

    const candidates = Array.from(section.querySelectorAll("p, span")).filter((element) => {
      if (element === aboutHeading || element.contains(aboutHeading) || aboutHeading.contains(element)) {
        return false;
      }

      return Boolean(aboutHeading.compareDocumentPosition(element) & Node.DOCUMENT_POSITION_FOLLOWING);
    }).map((element) => helpers.getNormalizedInnerText(element)).filter((text) => (
      !isNoiseText(text) && text !== "About"
    ));

    return candidates.find((text) => text.length >= 30) ?? candidates[0] ?? null;
  }

  function cleanName(fullName) {
    // The name heading often carries a trailing connection degree (e.g. "Jane Doe · 1st").
    return fullName.replace(/\s*·\s*(?:1st|2nd|3rd|\d+(?:st|nd|rd|th))\s*$/i, "").trim();
  }

  function splitName(fullName) {
    const parts = cleanName(fullName).split(/\s+/).filter(Boolean);
    if (parts.length === 0) {
      return {
        firstName: null,
        lastName: null
      };
    }

    return {
      firstName: parts[0] ?? null,
      lastName: parts.length > 1 ? parts.slice(1).join(" ") : null
    };
  }

  function findSectionByHeading(document, headingText) {
    const headings = Array.from(document.querySelectorAll("section h1, section h2, section h3, section h4"));
    const heading = headings.find((candidate) => (
      helpers.getNormalizedInnerText(candidate) === headingText
    ));

    return heading?.closest("section") ?? null;
  }

  function getExperienceEntries(document) {
    return getSectionEntries(document, "Experience", "profile_ExperienceTopLevelSection", 3);
  }

  function getSectionEntries(document, headingText, testIdPrefix, limit = Number.POSITIVE_INFINITY) {
    const section = findSectionByHeading(document, headingText);
    if (!section) {
      return [];
    }

    const collectionRoot = section.querySelector(`[data-testid^='${testIdPrefix}']`);
    if (!collectionRoot) {
      return [];
    }

    return Array.from(collectionRoot.children)
      .filter((entry) => entry.getAttribute("componentkey")?.startsWith("entity-collection-item"))
      .slice(0, limit);
  }

  function sanitizeExpandableText(text) {
    if (!text) {
      return null;
    }

    const sanitized = text
      .replace(/\u2026\s*more$/i, "")
      .replace(/\s+more$/i, "")
      .trim();

    return sanitized || null;
  }

  function getExpandableText(container) {
    const expandable = container?.querySelector("[data-testid='expandable-text-box']");
    if (!expandable) {
      return null;
    }

    const clone = expandable.cloneNode(true);
    clone.querySelectorAll("button").forEach((button) => button.remove());
    return sanitizeExpandableText(helpers.getNormalizedInnerText(clone));
  }

  function looksLikeDurationLine(text) {
    return /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b/i.test(text)
      && /\s-\s/i.test(text);
  }

  function extractYearsFromDuration(durationLine) {
    const yearsMatch = durationLine?.match(/·\s*(\d+)\s+yr/i);
    if (yearsMatch) {
      return Number.parseInt(yearsMatch[1], 10);
    }

    const monthsOnlyMatch = durationLine?.match(/·\s*(\d+)\s+mos?/i);
    if (monthsOnlyMatch) {
      return 0;
    }

    return 0;
  }

  function extractCompany(companyLine) {
    if (!companyLine) {
      return null;
    }

    return companyLine.split(" · ")[0]?.trim() || null;
  }

  function extractExperience(entry) {
    const textParagraphs = Array.from(entry.querySelectorAll("p"))
      .map((paragraph) => helpers.getNormalizedInnerText(paragraph))
      .filter(Boolean);

    const title = textParagraphs[0] ?? null;
    const companyLine = textParagraphs[1] ?? null;
    const durationIndex = textParagraphs.findIndex((text, index) => index >= 2 && looksLikeDurationLine(text));
    const durationLine = durationIndex >= 0 ? textParagraphs[durationIndex] : null;
    const locationCandidate = durationIndex >= 0 ? textParagraphs[durationIndex + 1] ?? null : null;

    if (!title || !companyLine || !durationLine) {
      return null;
    }

    return {
      job_title: title,
      company: extractCompany(companyLine),
      time_employed_years: extractYearsFromDuration(durationLine),
      is_actively_working: /\bPresent\b/i.test(durationLine),
      job_location: looksLikeLocation(locationCandidate) ? locationCandidate : null,
      about: getExpandableText(entry)
    };
  }

  function extractExperiences(document) {
    return getExperienceEntries(document)
      .map((entry) => extractExperience(entry))
      .filter(Boolean);
  }

  function getEducationEntries(document) {
    return getSectionEntries(document, "Education", "profile_EducationTopLevelSection");
  }

  function looksLikeYearLine(text) {
    return /\b(?:19|20)\d{2}\b/.test(text);
  }

  function extractLastYearAttended(yearLine) {
    const years = yearLine?.match(/\b(?:19|20)\d{2}\b/g) ?? [];
    if (years.length === 0) {
      return null;
    }

    return Number.parseInt(years[years.length - 1], 10);
  }

  function normalizeDegree(text) {
    if (!text || looksLikeYearLine(text)) {
      return null;
    }

    return text;
  }

  function extractEducation(entry) {
    const textParagraphs = Array.from(entry.querySelectorAll("p"))
      .map((paragraph) => helpers.getNormalizedInnerText(paragraph))
      .filter(Boolean);

    const schoolName = textParagraphs[0] ?? null;
    const yearLine = textParagraphs.find((text, index) => index >= 1 && looksLikeYearLine(text)) ?? null;
    const yearLineIndex = yearLine ? textParagraphs.indexOf(yearLine) : -1;
    const degreeCandidate = yearLineIndex > 1
      ? textParagraphs.slice(1, yearLineIndex).find((text) => !looksLikeYearLine(text)) ?? null
      : textParagraphs[1] ?? null;

    if (!schoolName) {
      return null;
    }

    return {
      university_school_name: schoolName,
      degree_domain: normalizeDegree(degreeCandidate),
      last_year_attended: extractLastYearAttended(yearLine)
    };
  }

  function extractEducationItems(document) {
    return getEducationEntries(document)
      .map((entry) => extractEducation(entry))
      .filter(Boolean);
  }

  function parseLinkedInProfile({ document, url }) {
    const profilePathname = getProfilePathname(url);
    const nameElement = findNameElement(document, profilePathname);

    if (!nameElement) {
      throw new Error("Unable to find the LinkedIn profile name.");
    }

    const fullName = helpers.getNormalizedInnerText(nameElement);
    if (!fullName) {
      throw new Error("Unable to read the LinkedIn profile name.");
    }

    const headerRoot = findHeaderRoot(nameElement);
    const location = extractLocation(headerRoot, nameElement);
    const { firstName, lastName } = splitName(fullName);

    return JSON.stringify(
      {
        first_name: firstName,
        last_name: lastName,
        headline: extractHeadline(headerRoot, nameElement, location),
        location,
        about: extractAbout(document),
        experience: extractExperiences(document),
        education: extractEducationItems(document)
      },
      null,
      2
    );
  }

  namespace.registerParser({
    id: "linkedin-profile",
    matches: (url) => {
      try {
        const parsedUrl = new URL(url);
        return /^https:\/\/(?:www\.)?linkedin\.com$/i.test(parsedUrl.origin)
          && isProfilePathname(parsedUrl.pathname);
      } catch (_error) {
        return false;
      }
    },
    parse: parseLinkedInProfile
  });
})();
