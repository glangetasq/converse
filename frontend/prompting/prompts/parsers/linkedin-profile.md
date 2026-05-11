LinkedIn profile context and task:

- The page is a LinkedIn profile page, not an existing message thread.
- Write suggestions as short LinkedIn introduction snippets the extension user could send as an opening outreach message.
- Each suggestion must be message-ready, concise, and natural on LinkedIn.
- Hard limit: each suggestion must be 300 characters or fewer, even if the user asks for something longer.
- Use the profile details only when they help the opener feel specific and credible. Do not overstuff the message with every parsed field.
- Prefer a light introduction or reason for reaching out over a full sales pitch, long backstory, or multi-step message.
- Avoid generic networking cliches, exaggerated enthusiasm, or wording that sounds mass-produced.
- Do not invent shared history, referrals, meetings, or familiarity that are not supported by the parsed profile or the user input.

Canonical snippet guidance:

- Your first instinct should be to reuse the most relevant snippet pattern below, not to write a brand new structure from scratch.
- Stay close to the wording, flow, and tone of the chosen snippet. Fill the gaps with profile-specific details, light customization, and cleaner transitions.
- Keep the spirit of the snippet intact. Do not noticeably change the tone, level of warmth, or overall intent.
- Replace placeholders like Name, XXX, and YYY with details inferred from the profile when possible.
- If a field is unavailable, keep the message natural and simply omit that detail rather than inventing one.

<base_data_science_english>
Hi Name,

I'm Quentin - a Columbia alum and DS/MLE at Goldman Sachs. I'm looking to move into a more product-driven role, so your background in XXX at YYY is especially interesting to me.

I'd love to connect and ask you a few questions about your role and experience.
</base_data_science_english>

<french_alumn>
Hello Name,

Je m'appelle Quentin, ancien ENSAE/Columbia et DS/MLE chez Goldman Sachs. En ce moment, je cherche a evoluer vers un role plus product oriented.

J'aimerais beaucoup echanger avec toi et te poser quelques questions sur ton experience chez YYY, si tu es disponible 🙂
</french_alumn>

<headhunter>
Hi Name,

I'm Quentin - a Senior DS/MLE at Goldman Sachs and looking to move into a more product-focused role.

I'd like to ask you for some market color and whether you're working on any opportunities that could be a strong fit. Would love to connect and see if we could work together.
</headhunter>

Snippet selection rules:

- First infer whether the profile is genuinely French with high confidence.
- Only use the French snippet if the profile is genuinely French with high confidence.
- High confidence should come from multiple strong signals such as French language, French education, French work history, French location, or clearly French professional context.
- If the profile is ambiguous, international, or only weakly French, default to English.
- If the profile is French, use the `french_alumn` snippet as the main inspiration.

- If the profile is not confidently French, default to English and choose the closest English pattern below:
- 1. If the person appears to be a headhunter or agency recruiter, use `headhunter` as the main inspiration.
- 2. If the person appears to be an internal recruiter or talent acquisition profile, stay close to `headhunter` but adapt it to an in-house recruiting context rather than agency search language.
- 3. If the person appears to be a very senior DS/ML stakeholder or leader, stay close to `base_data_science_english` but orient the message more toward strategy, org, culture, scope, and high-level experience rather than technical details.
- 4. If the person appears to be a junior-to-senior DS/MLE/Data Engineer individual contributor, use `base_data_science_english` as the main inspiration.

Customization rules:

- Customize the chosen snippet with the person's experience, company, role, or background when that makes the message feel more specific.
- Keep the customization light. The goal is "mostly the existing snippet, plus relevant profile-aware filling of the gaps."
- Do not over-personalize or add details that make the opener feel overly researched.
- When multiple profile details are available, pick the one or two that best justify the outreach.
- If the message is aimed at a senior leader, avoid diving into technical implementation detail unless the profile strongly suggests that would be natural.
