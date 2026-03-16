#!/usr/bin/env node

/**
 * Sage CLI Installer
 *
 * Usage:
 *   npx sage-kit init                    # Interactive setup
 *   npx sage-kit init --platform claude-code --constitution startup --yes
 *   npx sage-kit init /path/to/project
 *   npx sage-kit status                  # Show project Sage state
 *   npx sage-kit help                    # Show usage
 */

import { createInterface } from 'readline';
import { existsSync, mkdirSync, cpSync, writeFileSync, readFileSync, readdirSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const Sage_ROOT = resolve(__dirname, '..');
const REPO_ROOT = resolve(Sage_ROOT, '..');

// ─── Colors (ANSI, no dependencies) ───────────────────────────────────────

const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  dim: '\x1b[2m',
  green: '\x1b[32m',
  blue: '\x1b[34m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  magenta: '\x1b[35m',
};

function banner() {
  console.log(`
${c.bold}${c.cyan}  ╔═══════════════════════════════════════════════════╗
  ║                                                   ║
  ║   ⚒️  Sage                                        ║
  ║   Framework for Orchestrated, Resilient,           ║
  ║   Governed Engineering                             ║
  ║                                                   ║
  ╚═══════════════════════════════════════════════════╝${c.reset}

  ${c.dim}Adaptive AI-driven development: FIX • BUILD • ARCHITECT${c.reset}
`);
}

// ─── Readline Prompting ───────────────────────────────────────────────────

function createPrompt() {
  return createInterface({ input: process.stdin, output: process.stdout });
}

function ask(rl, question) {
  return new Promise((resolve) => {
    rl.question(question, (answer) => resolve(answer.trim()));
  });
}

async function select(rl, question, options) {
  console.log(`\n${c.bold}${question}${c.reset}`);
  options.forEach((opt, i) => {
    console.log(`  ${c.cyan}${i + 1}${c.reset}) ${opt.label}${opt.desc ? c.dim + ' — ' + opt.desc + c.reset : ''}`);
  });
  const answer = await ask(rl, `\n${c.bold}Choose [1-${options.length}]:${c.reset} `);
  const idx = parseInt(answer, 10) - 1;
  if (idx >= 0 && idx < options.length) return options[idx].value;
  console.log(`${c.yellow}Invalid choice, using default: ${options[0].value}${c.reset}`);
  return options[0].value;
}

async function confirm(rl, question, defaultYes = true) {
  const hint = defaultYes ? '[Y/n]' : '[y/N]';
  const answer = await ask(rl, `${question} ${c.dim}${hint}${c.reset} `);
  if (answer === '') return defaultYes;
  return answer.toLowerCase().startsWith('y');
}

// ─── Parse CLI Arguments ──────────────────────────────────────────────────

function parseArgs(args) {
  const parsed = {
    command: null,
    directory: '.',
    platform: null,
    constitution: null,
    packs: [],
    yes: false,
    help: false,
  };

  let i = 0;
  while (i < args.length) {
    const arg = args[i];
    if (arg === 'init' || arg === 'status' || arg === 'help') {
      parsed.command = arg;
    } else if (arg === '--platform' && args[i + 1]) {
      parsed.platform = args[++i];
    } else if (arg === '--constitution' && args[i + 1]) {
      parsed.constitution = args[++i];
    } else if (arg === '--extensions' && args[i + 1]) {
      parsed.extensions = args[++i].split(',').map(s => s.trim());
    } else if (arg === '--yes' || arg === '-y') {
      parsed.yes = true;
    } else if (arg === '--help' || arg === '-h') {
      parsed.help = true;
    } else if (arg === '--directory' && args[i + 1]) {
      parsed.directory = args[++i];
    } else if (!arg.startsWith('-') && !parsed.command) {
      // Might be a directory path or command
      if (['init', 'status', 'help'].includes(arg)) {
        parsed.command = arg;
      }
    } else if (!arg.startsWith('-') && parsed.command === 'init') {
      parsed.directory = arg;
    }
    i++;
  }

  return parsed;
}

// ─── File Operations ──────────────────────────────────────────────────────

function ensureDir(dir) {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function copyDir(src, dest) {
  if (existsSync(src)) {
    cpSync(src, dest, { recursive: true, force: false });
  }
}

function copyFile(src, dest) {
  if (existsSync(src) && !existsSync(dest)) {
    const destDir = dirname(dest);
    ensureDir(destDir);
    cpSync(src, dest);
  }
}

// ─── Installation Logic ──────────────────────────────────────────────────

function installCore(projectDir, sageDir) {
  console.log(`\n${c.blue}Installing core framework...${c.reset}`);

  // Create .sage directory structure
  const dirs = [
    'skills', 'workflows', 'sub-workflows', 'gates', 'gates/_config',
    'agents', 'templates', 'tools', 'features', 'specs',
  ];
  dirs.forEach(d => ensureDir(join(sageDir, d)));

  // Copy core skills
  const skillsRoot = join(REPO_ROOT, 'skills');
  if (existsSync(skillsRoot)) {
    copyDir(skillsRoot, join(sageDir, 'skills'));
    console.log(`  ${c.green}✓${c.reset} Skills installed (12 core skills)`);
  }

  // Copy workflows
  const workflowsRoot = join(REPO_ROOT, 'workflows');
  if (existsSync(workflowsRoot)) {
    copyDir(workflowsRoot, join(sageDir, 'workflows'));
    console.log(`  ${c.green}✓${c.reset} Workflows installed (3 core + 1 sub-workflow)`);
  }

  // Copy gates
  const gatesRoot = join(REPO_ROOT, 'gates');
  if (existsSync(gatesRoot)) {
    copyDir(gatesRoot, join(sageDir, 'gates'));
    console.log(`  ${c.green}✓${c.reset} Quality gates installed (5 default gates)`);
  }

  // Copy agents
  const agentsRoot = join(REPO_ROOT, 'agents');
  if (existsSync(agentsRoot)) {
    copyDir(agentsRoot, join(sageDir, 'agents'));
    console.log(`  ${c.green}✓${c.reset} Personas installed (5 default personas)`);
  }

  // Copy templates
  const templatesRoot = join(REPO_ROOT, 'templates');
  if (existsSync(templatesRoot)) {
    copyDir(templatesRoot, join(sageDir, 'templates'));
    console.log(`  ${c.green}✓${c.reset} Templates installed (5 default templates)`);
  }

  // Copy tools
  const toolsRoot = join(REPO_ROOT, 'tools');
  if (existsSync(toolsRoot)) {
    copyDir(toolsRoot, join(sageDir, 'tools'));
    // Make tools executable
    try {
      execSync(`chmod +x "${join(sageDir, 'tools')}"/*.sh 2>/dev/null || true`, { stdio: 'ignore' });
    } catch (e) { /* Windows — chmod not available */ }
    console.log(`  ${c.green}✓${c.reset} Tools installed (4 lifecycle scripts)`);
  }

  // Copy core contracts (for reference)
  const coreRoot = join(REPO_ROOT, 'core');
  if (existsSync(coreRoot)) {
    copyDir(coreRoot, join(sageDir, 'core'));
    console.log(`  ${c.green}✓${c.reset} Core contracts installed (8 contracts)`);
  }
}

function installConstitution(sageDir, constitutionName) {
  console.log(`\n${c.blue}Setting up constitution: ${constitutionName}...${c.reset}`);

  // Copy base constitution
  const baseSrc = join(REPO_ROOT, 'constitution', 'base.constitution.md');
  if (existsSync(baseSrc)) {
    copyFile(baseSrc, join(sageDir, 'constitution', 'base.constitution.md'));
  }

  // Generate project constitution that extends the chosen starter
  const constitutionContent = `---
name: project
tier: 2
version: "1.0.0"
extends: ${constitutionName}
---

# Project Constitution

Extends the **${constitutionName}** preset constitution.

## Additions

<!-- Add your project-specific principles here.
Each principle should be enforceable — if a quality gate can't check it,
it shouldn't be a principle. -->

## Waivers

<!-- Document any exemptions from inherited principles here.
Each waiver needs: reason, scope, approved-by, expires. -->
`;

  writeFileSync(join(sageDir, 'constitution.md'), constitutionContent);

  // Copy the preset constitution for reference
  const starterSrc = join(REPO_ROOT, 'constitution', 'presets', `${constitutionName}.constitution.md`);
  if (existsSync(starterSrc)) {
    ensureDir(join(sageDir, 'constitution', 'presets'));
    copyFile(starterSrc, join(sageDir, 'constitution', 'presets', `${constitutionName}.constitution.md`));
  }

  console.log(`  ${c.green}✓${c.reset} Constitution created: .sage/constitution.md (extends: ${constitutionName})`);
}

function installPlatform(projectDir, sageDir, platformName) {
  console.log(`\n${c.blue}Setting up ${platformName} adapter...${c.reset}`);

  if (platformName === 'claude-code' || platformName === 'codex') {
    // Claude Code / Codex use CLAUDE.md as the primary system prompt
    const claudeMd = generateClaudeCodeMd(platformName);
    writeFileSync(join(projectDir, 'CLAUDE.md'), claudeMd);
    console.log(`  ${c.green}✓${c.reset} CLAUDE.md installed (system prompt for ${platformName})`);

    // Also copy .claude-plugin for slash commands (if supported)
    const pluginSrc = join(REPO_ROOT, 'platforms', 'claude-code', '.claude-plugin');
    const pluginDest = join(projectDir, '.claude-plugin');
    if (existsSync(pluginSrc)) {
      copyDir(pluginSrc, pluginDest);
    }

    // Copy commands
    const cmdSrc = join(REPO_ROOT, 'platforms', 'claude-code', 'commands');
    const cmdDest = join(pluginDest, 'commands');
    if (existsSync(cmdSrc)) {
      copyDir(cmdSrc, cmdDest);
      try {
        execSync(`chmod +x "${cmdDest}"/*.sh 2>/dev/null`, { stdio: 'ignore' });
      } catch (_) { /* Windows doesn't need chmod */ }
    }

    // Copy hooks
    const hooksSrc = join(REPO_ROOT, 'platforms', 'claude-code', 'hooks');
    const hooksDest = join(pluginDest, 'hooks');
    if (existsSync(hooksSrc)) {
      copyDir(hooksSrc, hooksDest);
      try {
        execSync(`chmod +x "${hooksDest}"/*.sh 2>/dev/null`, { stdio: 'ignore' });
      } catch (_) { /* Windows */ }
    }

    console.log(`  ${c.green}✓${c.reset} Slash commands and hooks installed`);
    console.log(`  ${c.green}✓${c.reset} Tier 1 platform ready: subagents, parallel execution, worktrees`);

  } else {
    // Generic / Tier 2 platform — copy system prompt to platform-specific location
    const claudeMdSrc = join(REPO_ROOT, 'platforms', 'generic', 'CLAUDE.md');
    if (existsSync(claudeMdSrc)) {
      const destName = platformName === 'copilot' ? '.github/copilot-instructions.md'
                     : platformName === 'cursor' ? '.cursor/rules/sage.md'
                     : 'CLAUDE.md';
      const dest = join(projectDir, destName);
      ensureDir(dirname(dest));
      copyFile(claudeMdSrc, dest);
      console.log(`  ${c.green}✓${c.reset} System prompt installed: ${destName}`);
    }
    console.log(`  ${c.green}✓${c.reset} Tier 2 platform ready: sequential execution, self-review`);
  }
}

function generateClaudeCodeMd(platformName) {
  return `# Sage — Framework for Orchestrated, Resilient, Governed Engineering

You are operating with the Sage framework. Read this file at the start of every session.

## How Sage Works

Sage adapts its weight to the work. Detect the mode from the user's request:

**FIX mode** (bugs, errors, typos — minutes):
  1. Read \`.sage/core/capabilities/debugging/systematic-debug/SKILL.md\`
  2. Read \`.sage/core/capabilities/execution/tdd/SKILL.md\`
  3. Follow: OBSERVE → HYPOTHESIZE → TEST → FIX (with TDD) → verify
  4. Run gates 04 (hallucination check) and 05 (verification) before committing

**BUILD mode** (features, components, refactors — hours):
  1. Read \`.sage/core/workflows/build.workflow.md\` for the full sequence
  2. Read each skill from \`.sage/skills/\` as the workflow references it
  3. Follow: codebase-scan → quick-elicit → specify → plan → implement task-by-task
  4. Run all 5 quality gates after each task implementation
  5. Pause for human approval at checkpoints (after spec, after plan, after completion)

**ARCHITECT mode** (new products, migrations, redesigns — days):
  1. Read \`.sage/core/workflows/architect.workflow.md\` for the full sequence
  2. Read all persona files from \`.sage/core/agents/\` for role-based thinking
  3. Full planning → architecture with ADRs → story decomposition → sprint execution
  4. Run all 5 quality gates + cross-feature consistency checks

If unsure which mode, default to BUILD.

## Mandatory Rules — NEVER VIOLATE

1. **Read the constitution first.** Before ANY work, read \`.sage/constitution.md\`
   AND \`.sage/core/constitution/base.constitution.md\`. The constitution is the highest
   authority. When any instruction conflicts with the constitution, the constitution wins.

2. **TDD is law.** Read \`.sage/core/capabilities/execution/tdd/SKILL.md\` before writing code.
   Write the test first. Watch it fail. Write minimal code. Watch it pass. Refactor.
   Code written before its test must be DELETED. No exceptions. No rationalizations.
   "It's too simple to test" is not valid. "I'll add tests later" is not valid.

3. **Quality gates are mandatory.** Read gate definitions in \`.sage/gates/\`.
   After implementing each task, run applicable gates. Never skip them.

4. **Scope guard is always active.** Read \`.sage/core/capabilities/context/scope-guard/SKILL.md\`.
   Do what was planned. Nothing more. "While I'm here" additions are forbidden.

5. **Verify before claiming done.** Run the tests. Show the output. Never say
   "tests should pass" — run them and prove it.

6. **Update the plan file after every task.** When you complete a task, check its
   checkbox in the plan file and add the commit hash. This IS the state persistence.
   If the session dies unexpectedly, the plan file shows exactly where things stand.
   progress.md is just a pointer — the plan file is the truth.

## Session Start Checklist

Every session, in order:
1. Read this file (CLAUDE.md)
2. Read \`.sage/constitution.md\`
3. Read \`.sage/progress.md\` — find the active feature and plan file path
4. Read the **plan file** — count checkboxes to see real progress
   - \`[x]\` = done, \`[ ]\` = not done, \`🔄\` = was in progress, \`🚫\` = blocked
5. Read \`.sage/conventions.md\` — project-specific patterns
6. Report to user: "Resuming [feature]. [N] of [M] tasks done. Next: [task]."
7. Continue from where the plan file shows work stopped

## State Persistence

The plan file IS the progress tracker. When you complete a task:
1. Check the box in the plan: \`- [ ]\` → \`- [x]\`
2. Add: \`✅ DONE (commit: abc1234)\`
3. Record gate results in the Gate Log table
4. Update \`.sage/progress.md\` as a lightweight pointer

This means progress is saved as a SIDE EFFECT of doing the work.
No separate "save" action that can be forgotten if the session dies.

## Project State Files

| File | Purpose | Truth Level |
|------|---------|-------------|
| \`.sage/features/<name>/plan.md\` | Task checkboxes, gate log — the REAL progress | **Ground truth** |
| \`.sage/progress.md\` | Pointer: active feature, mode, plan path | Quick orientation (may be stale) |
| \`.sage/constitution.md\` | Governance principles — always active | Always current |
| \`.sage/conventions.md\` | Discovered project patterns | Append-only |
| \`.sage/decisions.md\` | Architectural Decision Records | Append-only |
| \`.sage/config.yaml\` | Framework configuration | Always current |

## Skills Reference

Skills live in \`.sage/skills/\`. Read each skill BEFORE executing it:

| Category | Skills |
|----------|--------|
| Elicitation | \`codebase-scan\`, \`quick-elicit\` |
| Planning | \`specify\`, \`plan\` |
| Execution | \`tdd\` (mandatory), \`implement\` |
| Review | \`spec-review\` (mandatory), \`quality-review\` (mandatory) |
| Debugging | \`systematic-debug\`, \`verify-completion\` |
| Context | \`session-bridge\`, \`scope-guard\` (mandatory) |

## Tools

Deterministic scripts for structural operations. Call these instead of doing
the work manually — they're faster and more reliable:

| Tool | When to Use |
|------|-------------|
| \`bash .sage/runtime/tools/sage-new-feature.sh <slug>\` | Starting a new feature (creates dir + branch) |
| \`bash .sage/runtime/tools/sage-scaffold.sh <name> <mode>\` | After creating feature dir (copies templates) |
| \`bash .sage/runtime/tools/sage-check.sh\` | Verify prerequisites and project health |
| \`bash .sage/runtime/tools/sage-update-context.sh\` | After config changes (regenerates context) |

## Quality Gates

| Gate | File | When |
|------|------|------|
| 01 Spec Compliance | \`.sage/gates/01-spec-compliance.gate.md\` | BUILD, ARCHITECT |
| 02 Constitution | \`.sage/gates/02-constitution-compliance.gate.md\` | BUILD, ARCHITECT |
| 03 Code Quality | \`.sage/gates/03-code-quality.gate.md\` | BUILD, ARCHITECT |
| 04 Hallucination Check | \`.sage/gates/04-hallucination-check.gate.md\` | ALL modes |
| 05 Verification | \`.sage/gates/05-verification.gate.md\` | ALL modes |
`;
}

function generateConfig(sageDir, options) {
  const config = `# Sage Project Configuration
# See core/contracts/ for full documentation on each option.

# Mode detection
mode:
  default: build
  auto-detect: true

# Constitution
constitution:
  extends: ${options.constitution}

# Skills
skills:
  disabled: []
  replacements: {}

# Gates
gates:
  additional: []
  disabled: []

# Extensions
packs:
  enabled: [${options.extensions.join(', ')}]

# Playbooks
playbooks:
  enabled: []

# Adapter
platform: ${options.platform}

# Execution
execution:
  parallel: ${options.platform === 'claude-code' ? 'true' : 'false'}
  max-retries: 3

# Context
context:
  progressive: true
`;

  writeFileSync(join(sageDir, 'config.yaml'), config);
  console.log(`  ${c.green}✓${c.reset} Configuration generated: .sage/config.yaml`);
}

function initializeState(sageDir) {
  const progress = `# Progress

## Status
Mode: none
Feature: none
Phase: none
Last completed: Project initialized
Next action: Use /sage:help to see recommendations

## Completed
- [x] Sage framework installed

## Decisions Made
(none yet)

## Problems Encountered
(none yet)

## Updated
${new Date().toISOString()}
`;

  writeFileSync(join(sageDir, 'progress.md'), progress);
  writeFileSync(join(sageDir, 'decisions.md'), '# Architectural Decisions\n\n(none yet)\n');
  writeFileSync(join(sageDir, 'conventions.md'), '# Project Conventions\n\n(discovered automatically during codebase scans)\n');
}

// ─── Commands ─────────────────────────────────────────────────────────────

async function commandInit(args) {
  banner();

  const projectDir = resolve(args.directory);
  const sageDir = join(projectDir, '.sage');

  // Check if already initialized
  if (existsSync(sageDir)) {
    console.log(`${c.yellow}Warning: .sage/ already exists in ${projectDir}${c.reset}`);
    if (!args.yes) {
      const rl = createPrompt();
      const proceed = await confirm(rl, 'Merge with existing installation?', false);
      rl.close();
      if (!proceed) {
        console.log('Aborted.');
        process.exit(0);
      }
    }
  }

  let platform = args.platform;
  let constitution = args.constitution;
  let extensions = args.extensions;

  // Interactive mode
  if (!args.yes) {
    const rl = createPrompt();

    // Adapter selection
    if (!platform) {
      platform = await select(rl, 'Which AI coding tool are you using?', [
        { value: 'claude-code', label: 'Claude Code', desc: 'Tier 1 — full subagent support' },
        { value: 'codex',       label: 'Codex CLI',   desc: 'Tier 1 — subagent support' },
        { value: 'cursor',      label: 'Cursor',      desc: 'Tier 2 — rules file' },
        { value: 'copilot',     label: 'GitHub Copilot', desc: 'Tier 2 — instructions file' },
        { value: 'generic',     label: 'Other / Generic', desc: 'Tier 2 — CLAUDE.md system prompt' },
      ]);
    }

    // Constitution selection
    if (!constitution) {
      constitution = await select(rl, 'Choose a preset constitution:', [
        { value: 'startup',    label: 'Startup',     desc: 'Move fast, basic quality gates' },
        { value: 'enterprise', label: 'Enterprise',  desc: 'Full compliance, security, audit trails' },
        { value: 'opensource',  label: 'Open Source', desc: 'Docs, semver, license compliance' },
        { value: 'base',       label: 'Base Only',   desc: 'Just the 5 universal principles' },
      ]);
    }

    // Extensions
    if (extensions.length === 0) {
      console.log(`\n${c.bold}Enable domain extensions? (optional, can add later)${c.reset}`);
      console.log(`${c.dim}  Available: web, backend, security, devops, mobile, data${c.reset}`);
      const extAnswer = await ask(rl, `${c.bold}Extensions (comma-separated, or Enter to skip):${c.reset} `);
      if (extAnswer) {
        extensions = extAnswer.split(',').map(s => s.trim()).filter(Boolean);
      }
    }

    // Confirmation
    console.log(`\n${c.bold}── Installation Summary ──${c.reset}`);
    console.log(`  Directory:     ${projectDir}`);
    console.log(`  Platform:      ${platform} (Tier ${platform === 'claude-code' || platform === 'codex' ? '1' : '2'})`);
    console.log(`  Constitution:  ${constitution}`);
    console.log(`  Extensions:    ${extensions.length > 0 ? extensions.join(', ') : '(none)'}`);
    console.log('');

    const proceed = await confirm(rl, 'Proceed with installation?');
    rl.close();

    if (!proceed) {
      console.log('Aborted.');
      process.exit(0);
    }
  } else {
    // Non-interactive defaults
    platform = platform || 'claude-code';
    constitution = constitution || 'startup';
  }

  // ── Execute Installation ────────────────────────────────────────────
  console.log(`\n${c.bold}${c.green}Installing Sage...${c.reset}`);

  ensureDir(sageDir);
  installCore(projectDir, sageDir);
  installConstitution(sageDir, constitution);
  installPlatform(projectDir, sageDir, platform);
  generateConfig(sageDir, { platform, constitution, extensions });
  initializeState(sageDir);

  // ── Done ────────────────────────────────────────────────────────────
  console.log(`
${c.bold}${c.green}✓ Sage installed successfully!${c.reset}

${c.bold}Next steps:${c.reset}
  1. Open your AI coding tool in this directory
  2. ${platform === 'claude-code' ? 'Run /sage:help to see what to do next' : 'Ask the agent about Sage — it will read the system prompt automatically'}
  3. Edit ${c.cyan}.sage/constitution.md${c.reset} to add your project-specific principles

${c.bold}Quick start:${c.reset}
  ${c.cyan}/sage:fix${c.reset} "bug description"       Fix a bug in minutes
  ${c.cyan}/sage:build${c.reset} "feature description"  Build a feature in hours
  ${c.cyan}/sage:architect${c.reset} "product idea"     Plan a product in days

${c.dim}Everything in .sage/ is customizable. See .sage/core/contracts/ for module specs.${c.reset}
`);
}

function commandStatus() {
  const projectDir = process.cwd();
  const sageDir = join(projectDir, '.sage');

  if (!existsSync(sageDir)) {
    console.log(`${c.yellow}Sage not initialized in this directory.${c.reset}`);
    console.log(`Run: ${c.cyan}npx sage-kit init${c.reset}`);
    process.exit(1);
  }

  console.log(`${c.bold}Sage Status${c.reset}\n`);

  // Read config
  if (existsSync(join(sageDir, 'config.yaml'))) {
    const config = readFileSync(join(sageDir, 'config.yaml'), 'utf-8');
    const platform = config.match(/platform:\s*(\S+)/)?.[1] || 'unknown';
    const constitution = config.match(/extends:\s*(\S+)/)?.[1] || 'base';
    console.log(`  Platform:      ${platform}`);
    console.log(`  Constitution:  ${constitution}`);
  }

  // Read progress
  if (existsSync(join(sageDir, 'progress.md'))) {
    const progress = readFileSync(join(sageDir, 'progress.md'), 'utf-8');
    const mode = progress.match(/Mode:\s*(.+)/)?.[1] || 'none';
    const feature = progress.match(/Feature:\s*(.+)/)?.[1] || 'none';
    const next = progress.match(/Next action:\s*(.+)/)?.[1] || '';
    console.log(`  Mode:          ${mode}`);
    console.log(`  Feature:       ${feature}`);
    if (next) console.log(`  Next action:   ${next}`);
  }

  // Count modules
  const skillCount = readdirSync(join(sageDir, 'skills'), { recursive: true })
    .filter(f => f.toString().endsWith('SKILL.md')).length;
  console.log(`  Skills:        ${skillCount}`);
  console.log('');
}

function commandHelp() {
  banner();
  console.log(`${c.bold}Usage:${c.reset}

  ${c.cyan}npx sage-kit init${c.reset}                         Interactive setup
  ${c.cyan}npx sage-kit init /path/to/project${c.reset}        Initialize in specific directory
  ${c.cyan}npx sage-kit init --yes${c.reset}                   Non-interactive with defaults
  ${c.cyan}npx sage-kit status${c.reset}                       Show project Sage state
  ${c.cyan}npx sage-kit help${c.reset}                         This help

${c.bold}Options:${c.reset}

  --platform <name>          claude-code, codex, cursor, copilot, generic
  --constitution <name>     startup, enterprise, opensource, base
  --extensions <list>       Comma-separated: web,backend,security
  --directory <path>        Target directory (default: current)
  --yes, -y                 Skip prompts, use defaults

${c.bold}Examples:${c.reset}

  ${c.dim}# Interactive setup in current directory${c.reset}
  npx sage-kit init

  ${c.dim}# CI/CD: non-interactive with specific options${c.reset}
  npx sage-kit init --platform claude-code --constitution enterprise --yes

  ${c.dim}# New project in a new directory${c.reset}
  npx sage-kit init my-new-project --platform cursor --constitution startup
`);
}

// ─── Main ─────────────────────────────────────────────────────────────────

const args = parseArgs(process.argv.slice(2));

if (args.help || (!args.command && process.argv.length <= 2)) {
  commandHelp();
} else if (args.command === 'init') {
  commandInit(args).catch(err => {
    console.error(`${c.red}Error: ${err.message}${c.reset}`);
    process.exit(1);
  });
} else if (args.command === 'status') {
  commandStatus();
} else if (args.command === 'help') {
  commandHelp();
} else {
  console.log(`${c.red}Unknown command: ${args.command}${c.reset}`);
  console.log(`Run ${c.cyan}npx sage-kit help${c.reset} for usage.`);
  process.exit(1);
}
