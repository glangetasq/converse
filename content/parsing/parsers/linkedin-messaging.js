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

    const eventItems = messageList.matches("li.msg-s-message-list__event")
      ? [messageList]
      : Array.from(messageList.querySelectorAll("li.msg-s-message-list__event"));

    for (const eventItem of eventItems) {
      const dateHeading = helpers.getFirstMatchText(eventItem, ":scope > time.msg-s-message-list__time-heading");
      if (dateHeading) {
        currentDate = dateHeading;
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
          date: currentDate,
          sender,
          time,
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
