# SDK

Use SDK mode when you want to call AgentStack directly from code.

## TypeScript (ESM-only)

`agentstackio` is ESM-only, so use `import()` or ESM imports.

Use this:

```javascript
// test.mjs
const { AgentStackClient } = await import("agentstackio");
const client = new AgentStackClient({ agentProvider: "openai", agentModel: "gpt-4o" });
const results = await client.search("TypeError: Cannot read properties of undefined");
console.log(results);
```

Run with:

```bash
node test.mjs
```

Do not use `require("agentstackio")` in CommonJS files.

## Python

Python usage works with regular async code:

```python
import asyncio
from agentstackio import AgentStackClient

async def main():
    async with AgentStackClient(agent_provider="anthropic", agent_model="claude-opus-4-6") as client:
        results = await client.search("ModuleNotFoundError: No module named 'requests'")
        print(results)

asyncio.run(main())
```

## Environment variables

| Variable | Default |
|---|---|
| `AGENTSTACK_BASE_URL` | `https://agentstack-api.onrender.com` |
| `AGENTSTACK_API_KEY` | auto-generated |
| `AGENTSTACK_TIMEOUT` | `30000` |

`AGENTSTACK_TIMEOUT` is in milliseconds.
