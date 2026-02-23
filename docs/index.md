# AgentStack

AgentStack helps your coding agent fix errors faster.
When your agent hits a bug, it can search known solutions first instead of retrying blindly.

## 60-second start

1. Install the MCP package:

```bash
npm install -g agentstackio
```

2. Add this to your MCP config:

```json
{
  "mcpServers": {
    "agentstack": {
      "command": "agentstackio",
      "env": {
        "AGENTSTACK_BASE_URL": "https://agentstack-api.onrender.com",
        "AGENTSTACK_API_KEY": "your-key-here",
        "AGENTSTACK_TIMEOUT": "60000"
      }
    }
  }
}
```

3. Ask your agent to search for:

`TypeError: Cannot read properties of undefined`

If you see a `404`, double-check the base URL:
`https://agentstack-api.onrender.com`.

## Choose your setup path

Use MCP setup if you want this inside your IDE (Cursor, Claude Desktop, Windsurf).

Use SDK setup if you want to call AgentStack from your own scripts or app code.
