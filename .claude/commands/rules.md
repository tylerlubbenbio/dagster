Add a critical rule learned from a mistake or blocker you just encountered.

Append to: `AGENT_KNOWLEDGE/RULES.md` in the current working directory. If there is already a rule that is for this, then just enhance it. Don't duplicate your rules. 

Guidelines:
- Only add rules for critical mistakes that wasted significant time
- Max 1-2 rules per invocation - keep the file small
- Never delete existing rules - only append
- Be concise - one line per rule
- Format: `- [RULE]: the rule you need to follow`

Example:
- Never run `rm -rf` without explicit user confirmation
- Always check if service is running before modifying config
