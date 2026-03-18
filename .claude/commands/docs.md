Instructions: Go look at the docs subdirectory for this task you just completed. Find the subdirectory that is most relevant. Look at the current docs and update them with whatever you have completed. If there is nothing relevant to this, then create a new Dock. But this directory is supposed to be living breathing documentation of what is now not of what has happened in the past, so you must update any old information with new information 


**Save to `AGENT_KNOWLEDGE/docs/** Every doc must go in an subdirectory within the doc folder that makes the most sense for the project. Look at what is there first and if a folder is not present then make a new one for this doc :

1. **Check first, then act:**
   - Find the subdirectory that matches this task (see table above).
   - To see what's in that subdirectory: read only the **first 500 characters** and the **filename (title)** of each doc. Do not read full doc contents when scanning.
   - **If there is a doc that covers exactly this topic** → update it with current state.
   - **If there is no relevant doc** → create a new one. Do NOT update unrelated docs.
   - Only update docs that are directly about what you just did. Don't touch docs for other features.

**Every doc must have a 500-character summary at the top** (right after the title). This lets future scans quickly see what's in the file without reading it all. Format:
```markdown
# Doc Title

[~500 char summary of what this doc covers—architecture, key files, scope.]

---
```

Guidelines:
- Document current state, not the process
- Focus on what a future AI needs to understand or maintain this
- Include: file locations, key functions, config, dependencies
- Exclude: debugging steps, past bugs, irrelevant context
- Keep it brief - bullet points and code snippets
- Name the file descriptively


2. Also if anything has changed with our architecture or the vision then update these documents as well.

AGENT_KNOWLEDGE/ARCHITECTURE.md
AGENT_KNOWLEDGE/VISION.md


3. Add a critical rule learned from a mistake or blocker you just encountered.

Append to: `AGENT_KNOWLEDGE/RULES.md` in the current working directory. If there is already a rule that is for this, then just enhance it. Don't duplicate your rules. 

Guidelines:
- Make sure there isnt a rule for it already or one you can update before making a new rule. 
- Only add rules for critical mistakes that wasted significant time
- Max 1-4 rules per invocation - keep the file small
- Never delete existing rules - only append
- Be concise - one line per rule
- Format: `- [RULE]: the rule you need to follow`

Example:
- Never run `rm -rf` without explicit user confirmation
- Always check if service is running before modifying config
