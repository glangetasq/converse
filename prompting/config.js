(() => {
  globalThis.ConversePrompting = Object.freeze({
    globalPromptPath: "prompting/prompts/global.md",
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
        promptPath: "prompting/prompts/modes/cover-letter.md"
      })
    }),
    parserPromptPaths: Object.freeze({
      "linkedin-profile": "prompting/prompts/parsers/linkedin-profile.md",
      "linkedin-messaging": "prompting/prompts/parsers/linkedin-messaging.md"
    })
  });
})();
