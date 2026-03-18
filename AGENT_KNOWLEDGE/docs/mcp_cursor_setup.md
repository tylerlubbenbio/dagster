# MCP Cursor Setup

Config file: `~/.cursor/mcp.json` (user-level, not in repo).

## Required for macOS

Cursor spawns MCP processes with a minimal env. Without this, `spawn npx ENOENT` occurs.

- **Command**: Use full path to npx (e.g. `/opt/homebrew/bin/npx`), not bare `npx`
- **env.PATH**: Must include Node/bin so npx can find node. Example: `"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"`

## Servers

| Server | Package | Purpose |
|--------|---------|---------|
| warehouse | `@modelcontextprotocol/server-postgres` | Warehouse tables, schemas, queries |
| metabase | `@cognitionai/metabase-mcp-server` | Metabase dashboards, cards, DB metadata |
| dagster-postgres | `@modelcontextprotocol/server-postgres` | Dagster internal metadata (runs, failures, schedules) |

## Config structure

```json
{
  "mcpServers": {
    "warehouse": {
      "type": "stdio",
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "<connection_string>"],
      "env": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    },
    "metabase": {
      "type": "stdio",
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@cognitionai/metabase-mcp-server"],
      "env": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "METABASE_URL": "<url>",
        "METABASE_API_KEY": "<key>"
      }
    },
    "dagster-postgres": {
      "type": "stdio",
      "command": "/opt/homebrew/bin/npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "<dagster_db_connection_string>"],
      "env": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
      }
    }
  }
}
```

## Accessing Dagster Postgres (Kubernetes)

If Dagster's internal Postgres runs in Kubernetes, port-forward before using the dagster-postgres MCP:

```bash
kubectl port-forward svc/dagster-postgresql -n {{K8S_NAMESPACE}} --context prod 5433:5432 &
```

Then connect via `localhost:5433`.

## Troubleshooting

- **ENOENT**: Add PATH to env and use full path to npx
- **Restart Cursor** after config changes
- **Context7** is a plugin — configure via Cursor Settings > Extensions
