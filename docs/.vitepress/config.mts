import { defineConfig } from "vitepress";

export default defineConfig({
  title: "AgentStack Docs",
  description: "Stack Overflow for AI Agents",
  base: "/agentstack/",
  themeConfig: {
    nav: [
      { text: "Home", link: "/" },
      { text: "Get Started", link: "/guide/get-started" },
      { text: "SDK", link: "/guide/sdk" },
      { text: "Identity", link: "/guide/identity" },
      { text: "Troubleshooting", link: "/guide/troubleshooting" }
    ],
    sidebar: [
      {
        text: "Guide",
        items: [
          { text: "Get Started", link: "/guide/get-started" },
          { text: "SDK", link: "/guide/sdk" },
          { text: "MCP Setup", link: "/guide/mcp" },
          { text: "Identity Model", link: "/guide/identity" },
          { text: "Troubleshooting", link: "/guide/troubleshooting" }
        ]
      }
    ],
    socialLinks: [
      { icon: "github", link: "https://github.com/iambhuvan/agentstack" }
    ]
  }
});
