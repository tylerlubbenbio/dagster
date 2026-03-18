Here's the updated prompt that **strips `model`** entirely (since Cursor auto-selects):

```
You are an expert at converting Claude Code agent files (.claude/agents/*.md) to Cursor SKILL.md format.

RULES:
1. Parse the YAML frontmatter from the input Claude agent file
2. Map ONLY these keys to Cursor SKILL.md:
   - `name` → `name` (direct copy)
   - `description` → `description` (append `invocation-trigger` if present) 
   - `user-invoked: false` → `disable-model-invocation: true`
3. **STRIP `model` completely** - Cursor uses workspace auto-model, never include it
4. Preserve OTHER keys as custom metadata (type, context, can-parallelize, etc.)
5. Keep the entire Markdown BODY unchanged
6. Output path: `.cursor/skills/{name-lowercase-with-dashes}/SKILL.md`

INPUT FORMAT:
```
***
[FRONTMATTER YAML]
***
[BODY MARKDOWN]
```

OUTPUT EXACTLY:
```
***
[NEW FRONTMATTER YAML - sorted alphabetically, NO model key]
***
[BODY - unchanged]

DIRECTORY: .cursor/skills/{name}/SKILL.md
```

EXAMPLE:
INPUT:
```
***
name: cortex-intelligence
type: agent-skill  
description: Builds Cortex pipelines
model: sonnet
user-invoked: false
invocation-trigger: When creating scrapers
***
# Instructions...
```

OUTPUT:
```
***
description: Builds Cortex pipelines. Use when creating scrapers.
disable-model-invocation: true
name: cortex-intelligence
type: agent-skill
***
# Instructions...

DIRECTORY: .cursor/skills/cortex-intelligence/SKILL.md
```

Convert this Claude agent file:
```
[PASTE YOUR FILE HERE]
```
```

**Key change:** Rule #3 now **explicitly strips `model`** - output will never include it, letting Cursor use your workspace default (Sonnet/etc.). All other metadata preserved. Ready to use!