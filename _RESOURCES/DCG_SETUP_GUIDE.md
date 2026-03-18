# Destructive Command Guard (DCG) Setup Guide

## Overview

**Destructive Command Guard (dcg)** is a security tool that prevents catastrophic commands from executing. It's designed to protect AI coding agents (like Claude Code) from accidentally running dangerous operations that could destroy your codebase.

**Why this matters:** Claude Code agents run Bash commands autonomously. Without protection, a bug or misunderstanding could lead to:
- Accidental `git reset --hard` (losing all uncommitted work)
- `git push --force` (overwriting remote history)
- `rm -rf` deletions (destroying files)
- Database drops (losing data)
- Kubernetes cluster deletions

DCG acts as a safety net by intercepting these commands **before** execution.

---

## Method Used: Grep-Based Pattern Matching (No Binary Required)

> **Note:** The DCG binary (v0.2.15) requires GLIBC_2.39+, which is not available on older Linux servers (Ubuntu 22.04 and below). The grep-based approach below provides equivalent protection without the binary dependency.

### Step 1: Create the Hook Directory
```bash
mkdir -p .claude/hooks
```

### Step 2: Create DCG Protection Hook

Create `.claude/hooks/dcg-protection.sh`:

```bash
#!/bin/bash
# Destructive Command Guard (dcg) Integration Hook
# Blocks catastrophic commands before they execute
# Uses pattern matching (dcg binary not required)

set -euo pipefail

# Read hook input from stdin
input=$(cat)

tool_name=$(echo "$input" | jq -r '.tool_name // empty')

# Only validate Bash commands
if [[ "$tool_name" != "Bash" ]]; then
  exit 0
fi

# Extract the command
cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

if [ -z "$cmd" ]; then
  exit 0
fi

# Block dangerous patterns
if echo "$cmd" | grep -Eiq 'git reset --hard|git push.*--force|git clean.*-f|rm -rf|drop database|truncate table|docker system prune|kubectl delete'; then
  echo "BLOCKED BY DCG: Destructive command detected and prevented" >&2
  echo "Command: $cmd" >&2
  exit 2
fi

exit 0
```

Make it executable:
```bash
chmod +x .claude/hooks/dcg-protection.sh
```

### Step 3: Update Claude Code Settings

Add to `.claude/settings.local.json` under `hooks.PreToolUse`:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": ".claude/hooks/dcg-protection.sh",
      "statusMessage": "🛡️  DCG: Validating command safety..."
    }
  ]
}
```

---

## What Gets Protected

| Command | Reason | Impact |
|---------|--------|--------|
| `git reset --hard` | Discards all uncommitted changes | **Loss of work** |
| `git push --force` | Overwrites remote history | **Data loss for team** |
| `git clean -f` | Deletes untracked files | **Loss of work** |
| `rm -rf` | Recursive deletion | **Data destruction** |
| `drop database` | Deletes database | **Complete data loss** |
| `truncate table` | Empties database table | **Data loss** |
| `docker system prune` | Removes all Docker resources | **Container loss** |
| `kubectl delete` | Deletes Kubernetes resources | **Service disruption** |

### Adding More Patterns

Edit the grep line in `dcg-protection.sh` and append new patterns separated by `|`:

```bash
if echo "$cmd" | grep -Eiq 'git reset --hard|git push.*--force|....|YOUR_NEW_PATTERN'; then
```

---

## Binary Installation (Alternative - Requires GLIBC 2.39+)

If your server has GLIBC 2.39+ (Ubuntu 24.04+), you can optionally install the DCG binary for its full pattern library:

```bash
mkdir -p ~/.local/bin
curl -fsSL "https://github.com/Dicklesworthstone/destructive_command_guard/releases/download/v0.2.15/dcg-x86_64-unknown-linux-gnu.tar.xz" -o /tmp/dcg.tar.xz
tar -xf /tmp/dcg.tar.xz -C ~/.local/bin
chmod +x ~/.local/bin/dcg
~/.local/bin/dcg --version
```

---

## Troubleshooting

### Hook Not Triggering

1. **Verify `.claude/settings.local.json` is valid JSON:**
   ```bash
   jq . .claude/settings.local.json
   ```

2. **Check hook file has execute permissions:**
   ```bash
   ls -la .claude/hooks/dcg-protection.sh
   # Should show: -rwxr-xr-x
   ```

3. **Verify jq is available:**
   ```bash
   jq --version
   ```

### GLIBC Error When Installing Binary

```
/root/.local/bin/dcg: /lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.39' not found
```

**Solution:** Use the grep-based approach above (no binary needed). The binary is optional.

---

## Testing the Hook Safely

**NEVER test with actual destructive commands** like `git reset --hard`, `rm -rf`, or `drop database`. If the hook fails for any reason, the command will execute and cause real damage.

**Safe test method — use `echo` to simulate the hook input directly:**

```bash
# This pipes fake JSON into the hook script. The "command" value is just a string
# being checked by grep — it never actually executes.
echo '{"tool_name":"Bash","tool_input":{"command":"echo fake-rm -rf test"}}' | bash .claude/hooks/dcg-protection.sh 2>&1
echo "Exit code: $?"
# Expected: "BLOCKED BY DCG" message, exit code 2

# Test that safe commands pass through:
echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | bash .claude/hooks/dcg-protection.sh 2>&1
echo "Exit code: $?"
# Expected: no output, exit code 0
```

**Why this is safe:** The hook only reads stdin JSON and runs `grep` on the command string. It does NOT execute the command itself. The `echo fake-rm -rf test` string triggers the pattern match without any risk.

**Do NOT run these as regular bash commands** — only pipe them into the hook script. If you run them as bash tool calls in Claude Code, the DCG hook itself will see the outer command string containing the dangerous pattern and block the entire call (which is actually correct behavior).

---

## Reference Links

- **DCG GitHub:** https://github.com/Dicklesworthstone/destructive_command_guard
- **Latest Releases:** https://github.com/Dicklesworthstone/destructive_command_guard/releases
