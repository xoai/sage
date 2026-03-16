# GitHub Repository Setup

## Pushing to GitHub

The repo root should contain `install.sh`, `bin/`, `core/`, `skills/`, etc.
directly — NOT wrapped in a `sage/` subdirectory.

If you extracted from the zip:

```bash
unzip sage-framework.zip
cd sage
git init
git add .
git commit -m "v1.0.0 — Initial release"
git remote add origin https://github.com/xoai/sage.git
git branch -M main
git push -u origin main
```

Verify the structure is correct at https://github.com/xoai/sage —
`install.sh`, `bin/`, `core/`, `README.md` should be visible at root.

## Repository Description

An intelligent skills framework for AI agents — from research to design to shipping code. Think clearly. Work thoroughly. Deliver excellence.

## Topics

ai-agents, skills-framework, ai-coding, claude-code, antigravity, gemini, product-management, ux-design, developer-tools, ai-workflow

## After Creating the Repo

1. Set the description and topics in Settings
2. Enable Issues
3. Enable Discussions (for community Q&A)
4. Set default branch to `main`
5. Test the install: `curl -fsSL https://raw.githubusercontent.com/xoai/sage/main/install.sh | bash`
6. Test the flow: `sage new test-app` → open in IDE → type `/sage`
