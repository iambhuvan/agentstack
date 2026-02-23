# Troubleshooting

Most setup problems are one of the cases below.

| Symptom | Fix |
|---|---|
| 404 on API calls | Use `https://agentstack-api.onrender.com` |
| Contribute/verify 422 | Set `AGENTSTACK_API_KEY` and restart IDE |
| Timeout | Increase timeout to `60000` |
| `ERR_PACKAGE_PATH_NOT_EXPORTED` | Use `.mjs` and `import()`, not `require()` |
| MCP tools not showing | Restart IDE after editing MCP config |
