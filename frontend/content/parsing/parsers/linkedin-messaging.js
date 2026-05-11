(() => {
  const namespace = globalThis.ConverseParsing;
  const helpers = namespace?.helpers;

  if (!namespace || !helpers) {
    throw new Error("LinkedIn parser loaded before runtime helpers.");
  }

  function extractHeadline(document) {
    const subtitle = helpers.getFirstMatchText(
      document,
      ".msg-thread__link-to-profile .msg-entity-lockup__entity-info"
    );

    if (!subtitle || helpers.isLikelyPresenceText(subtitle)) {
      return null;
    }

    return subtitle;
  }

  function extractHeadingMetadata(eventItem) {
    const headingText = helpers.getFirstMatchText(eventItem, ":scope > .msg-s-event-listitem--group-a11y-heading");
    if (!headingText) {
      return null;
    }

    const match = headingText.match(/^(.*?) sent the following messages? at (.+)$/);
    if (!match) {
      return null;
    }

    return {
      sender: match[1].trim(),
      time: match[2].trim()
    };
  }

  function getBodyText(listItem) {
    return helpers.getFirstMatchText(
      listItem,
      ":scope .msg-s-event-listitem__message-bubble .msg-s-event-listitem__body"
    );
  }

  function getMessageList(document) {
    const selectors = [
      ".msg-s-message-list-content",
      ".msg-s-message-list",
      ".msg-s-message-list__event-list",
      "[id^='message-list-']",
      "[id*='message-list']",
      "ul[class*='msg-s-message-list']",
      "[role='list'][aria-label*='message' i]"
    ];

    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element?.matches?.("li.msg-s-message-list__event")) {
        return element;
      }

      if (element?.querySelector?.("li.msg-s-message-list__event")) {
        return element;
      }
    }

    return null;
  }

  function getMonthIndex(monthName) {
    const monthKey = String(monthName ?? "").slice(0, 3).toLowerCase();
    return {
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
    }[monthKey] ?? null;
  }

  function normalizeYear(yearText, fallbackYear) {
    if (!yearText) {
      return fallbackYear;
    }

    const year = Number(yearText);
    if (!Number.isFinite(year)) {
      return fallbackYear;
    }

    return year < 100 ? 2000 + year : year;
  }

  function formatCompactDate(date) {
    const weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const day = String(date.getDate()).padStart(2, "0");
    const year = String(date.getFullYear()).slice(-2);
    return `${weekdays[date.getDay()]}${day}${months[date.getMonth()]}${year}`;
  }

  function offsetDate(baseDate, dayOffset) {
    const date = new Date(baseDate);
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() + dayOffset);
    return date;
  }

  function getMostRecentPreviousWeekdayDate(baseDate, targetWeekday) {
    const currentWeekday = baseDate.getDay();
    const dayOffset = -(((currentWeekday - targetWeekday + 7) % 7) || 7);
    return offsetDate(baseDate, dayOffset);
  }

  function parseCompactLinkedInDateHeading(normalizedHeading) {
    const compactMatch = normalizedHeading.match(/^(?:(?:sun|mon|tue|wed|thu|fri|sat)\s*)?(\d{1,2})\s*([a-z]{3})\s*(\d{2}|\d{4})$/i);
    if (!compactMatch) {
      return null;
    }

    const monthIndex = getMonthIndex(compactMatch[2]);
    if (monthIndex === null) {
      return null;
    }

    return new Date(normalizeYear(compactMatch[3], new Date().getFullYear()), monthIndex, Number(compactMatch[1]), 12, 0, 0, 0);
  }

  function parseMonthDayHeading(normalizedHeading, baseDate) {
    const monthDayMatch = normalizedHeading.match(/^([a-z]{3,9})\.?\s+(\d{1,2})(?:,?\s+(\d{2}|\d{4}))?$/i);
    if (!monthDayMatch) {
      return null;
    }

    const monthIndex = getMonthIndex(monthDayMatch[1]);
    if (monthIndex === null) {
      return null;
    }

    const today = offsetDate(baseDate, 0);
    let year = normalizeYear(monthDayMatch[3], today.getFullYear());
    let date = new Date(year, monthIndex, Number(monthDayMatch[2]), 12, 0, 0, 0);

    if (!monthDayMatch[3] && date > today) {
      year -= 1;
      date = new Date(year, monthIndex, Number(monthDayMatch[2]), 12, 0, 0, 0);
    }

    return date;
  }

  function parseLinkedInDateHeading(dateHeading, baseDate = new Date()) {
    const normalizedHeading = String(dateHeading ?? "").replace(/\s+/g, " ").trim();
    if (!normalizedHeading) {
      return null;
    }

    const today = offsetDate(baseDate, 0);

    if (/^today$/i.test(normalizedHeading)) {
      return today;
    }

    if (/^yesterday$/i.test(normalizedHeading)) {
      return offsetDate(today, -1);
    }

    const weekdayIndexByName = {
      sunday: 0,
      sun: 0,
      monday: 1,
      mon: 1,
      tuesday: 2,
      tue: 2,
      wednesday: 3,
      wed: 3,
      thursday: 4,
      thu: 4,
      friday: 5,
      fri: 5,
      saturday: 6,
      sat: 6
    };
    const weekdayKey = normalizedHeading.toLowerCase();
    if (Object.prototype.hasOwnProperty.call(weekdayIndexByName, weekdayKey)) {
      return getMostRecentPreviousWeekdayDate(today, weekdayIndexByName[weekdayKey]);
    }

    return parseCompactLinkedInDateHeading(normalizedHeading)
      || parseMonthDayHeading(normalizedHeading, today);
  }

  function parseLinkedInTime(timeText) {
    const normalizedTime = String(timeText ?? "").replace(/\s+/g, " ").trim();
    const match = normalizedTime.match(/^(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?$/i);
    if (!match) {
      return null;
    }

    let hour = Number(match[1]);
    const minute = Number(match[2] ?? 0);
    const meridiem = match[3].toLowerCase();

    if (hour === 12) {
      hour = meridiem === "a" ? 0 : 12;
    } else if (meridiem === "p") {
      hour += 12;
    }

    return {
      hour,
      minute,
      label: `${Number(match[1])}:${String(minute).padStart(2, "0")}${meridiem}m`
    };
  }

  function formatLinkedInDateTime(date, timeText) {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
      return null;
    }

    const time = parseLinkedInTime(timeText);
    if (!time) {
      return `${formatCompactDate(date)} ${String(timeText ?? "").replace(/\s+/g, " ").trim()}`.trim();
    }

    const datetime = new Date(date);
    datetime.setHours(time.hour, time.minute, 0, 0);
    return `${formatCompactDate(datetime)} ${time.label}`;
  }

  function formatFallbackDateTime(dateText, timeText) {
    const normalizedDate = String(dateText ?? "").replace(/\s+/g, " ").trim();
    const time = parseLinkedInTime(timeText);
    const normalizedTime = time?.label || String(timeText ?? "").replace(/\s+/g, " ").trim();

    return [normalizedDate, normalizedTime].filter(Boolean).join(" ") || null;
  }

  function parseLinkedInMessaging({ document }) {
    const messageList = getMessageList(document);

    if (!messageList) {
      throw new Error("LinkedIn messaging message list was not found in the current DOM.");
    }

    const name = helpers.getFirstMatchText(
      document,
      ".msg-thread__link-to-profile .msg-entity-lockup__entity-title"
    );

    if (!name) {
      throw new Error("Unable to find the LinkedIn conversation participant name.");
    }

    const messages = [];
    let currentDate = null;
    let currentDateText = null;

    const eventItems = messageList.matches("li.msg-s-message-list__event")
      ? [messageList]
      : Array.from(messageList.querySelectorAll("li.msg-s-message-list__event"));

    for (const eventItem of eventItems) {
      const dateHeading = helpers.getFirstMatchText(eventItem, ":scope > time.msg-s-message-list__time-heading");
      if (dateHeading) {
        currentDateText = dateHeading;
        currentDate = parseLinkedInDateHeading(dateHeading);
      }

      const listItem = eventItem.querySelector(":scope > .msg-s-event-listitem");
      if (!listItem) {
        continue;
      }

      const bodyText = getBodyText(listItem);
      if (!bodyText) {
        continue;
      }

      const metadataRoot = listItem.querySelector(":scope > .msg-s-message-group__meta");
      const visibleSender = helpers.getFirstMatchText(metadataRoot, ".msg-s-message-group__name");
      const visibleTime = helpers.getFirstMatchText(metadataRoot, ".msg-s-message-group__timestamp");
      const headingMetadata = extractHeadingMetadata(eventItem);
      const sender = visibleSender || headingMetadata?.sender || null;
      const time = visibleTime || headingMetadata?.time || null;

      if (sender && time) {
        messages.push({
          datetime: formatLinkedInDateTime(currentDate, time) || formatFallbackDateTime(currentDateText, time),
          sender,
          message: bodyText
        });
        continue;
      }

      const previousMessage = messages[messages.length - 1];
      if (!previousMessage) {
        throw new Error("Encountered a message continuation without a preceding message group.");
      }

      previousMessage.message = helpers.appendMessageLine(previousMessage.message, bodyText);
    }

    if (messages.length === 0) {
      throw new Error("No LinkedIn messages were extracted from the current thread.");
    }

    return JSON.stringify(
      {
        name,
        headline: extractHeadline(document),
        messages
      },
      null,
      2
    );
  }

  namespace.registerParser({
    id: "linkedin-messaging",
    urlPrefixes: ["https://www.linkedin.com/messaging"],
    parse: parseLinkedInMessaging
  });
})();
