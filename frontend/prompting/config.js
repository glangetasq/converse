(() => {
  globalThis.ConversePrompting = Object.freeze({
    globalPromptPath: "frontend/prompting/prompts/global.md",
    modes: Object.freeze({
      auto: Object.freeze({
        id: "auto",
        label: "auto",
        parserId: null,
        promptPath: null
      }),
      "cover-letter": Object.freeze({
        id: "cover-letter",
        label: "cover letter",
        parserId: "job-posting",
        promptPath: "frontend/prompting/prompts/modes/cover-letter.md"
      })
    }),
    parserPromptPaths: Object.freeze({
      "linkedin-profile": "frontend/prompting/prompts/parsers/linkedin-profile.md",
      "linkedin-messaging": "frontend/prompting/prompts/parsers/linkedin-messaging.md"
    })
  });
})();
