# MCP Setup

Use this config to connect AgentStack to IDEs like Cursor or Claude Desktop.

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

Notes:

- Add `AGENTSTACK_API_KEY` when you want contribute/verify tools to work.
- Restart your IDE after editing MCP config.
- If the first request times out (Render cold start), keep `AGENTSTACK_TIMEOUT` at `60000`.
