# Claude Code tooling for a research / marketing / pitch workflow (no coding)

Sources (fetched 2026-11-10): skills https://code.claude.com/docs/en/skills.md ;
subagents https://code.claude.com/docs/en/sub-agents.md ;
memory https://code.claude.com/docs/en/memory.md ;
permissions https://code.claude.com/docs/en/permissions.md ;
settings https://code.claude.com/docs/en/settings.md ;
output styles https://code.claude.com/docs/en/output-styles.md ;
full settings keys https://code.claude.com/docs/en/settings-reference.md

Not verified in this pass: the WebSearch domain-specifier form (the permissions page lists WebSearch only as a bare tool name), and any `.agents/` skills directory (none appears in the docs read).

---

## 1. Skills

### Location and scope

| Scope | Path | Loads in |
|:--|:--|:--|
| Project | `<repo>/.claude/skills/<name>/SKILL.md` | Sessions in this repo; commit it to share |
| Personal | `~/.claude/skills/<name>/SKILL.md` | All projects on this machine |
| Nested | `<subdir>/.claude/skills/<name>/SKILL.md` | Sessions started in or below `<subdir>` |
| Plugin | `<plugin>/skills/<name>/SKILL.md` | Where the plugin is enabled, as `/plugin-name:skill-name` |

Project skills load from the start directory and every parent up to the repo root. Subdirectory skills load when Claude first works on files there.

**Commands are merged into skills.** `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both create `/deploy`. Existing command files keep working and accept the same frontmatter except `name` and `paths`. Docs say skills are preferred for new work because they support supporting files.

### Frontmatter (all optional; `description` recommended; unknown keys ignored; `---` must be line 1)

| Field | Type / default | Meaning |
|:--|:--|:--|
| `name` | string, defaults to dir name | Slash command name |
| `description` | string | What it does and when to use it. Front-load the key use case |
| `when_to_use` | string | Extra trigger phrases; appended to `description` in the listing |
| `argument-hint` | string | Autocomplete hint, e.g. `[topic] [audience]` |
| `arguments` | string or list | Named args for `$name` substitution |
| `disable-model-invocation` | bool, default `false` | `true`: only you can run it (use for side-effect actions) |
| `user-invocable` | bool, default `true` | `false`: hidden from `/` menu, Claude-only |
| `allowed-tools` | string or list | Tools allowed without asking during the invoking turn. Space- or comma-separated |
| `disallowed-tools` | string or list | Tools removed while the skill is active |
| `model` | string | Model for the turn (`/model` values or `inherit`) |
| `effort` | `low`/`medium`/`high`/`xhigh`/`max` | Effort for the turn |
| `context` | `fork` | Run in a forked subagent |
| `agent` | string | Subagent type when `context: fork`: `Explore`, `Plan`, `general-purpose` (default), or a name from `.claude/agents/` |
| `background` | bool, default `true` | With `context: fork`; `false` waits for the result |
| `paths` | glob string or list | Auto-load only when working with matching files |
| `hooks` | object | Hooks active for the rest of the session once invoked |
| `shell` | `bash` / `powershell` | Shell for `` !`cmd` `` injection |
| `metadata`, `license`, `compatibility` | misc | Accepted; not acted on by Claude Code |

Substitutions: `$ARGUMENTS`, `$ARGUMENTS[N]`, `$0`/`$1` (0-based), `$name` (from `arguments`), `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`, `${CLAUDE_SESSION_ID}`. Escape a literal dollar with `\$`.

### Supporting files and size

```text
.claude/skills/source-review/
├── SKILL.md            required; overview + navigation, keep under 500 lines
├── source-scoring.md   loaded only when SKILL.md points to it
├── templates/brief.md  loaded when needed
└── scripts/check.py    executed, not loaded into context
```

Reference them from SKILL.md:

```markdown
## Additional resources
- Scoring rubric: [source-scoring.md](source-scoring.md)
- Output template: [templates/brief.md](templates/brief.md)
```

### Invocation

- Default: you type `/name`, or Claude loads it when the request matches `description`. Only the description sits in context until invoked.
- `disable-model-invocation: true`: manual only; description is not in context.
- `user-invocable: false`: Claude only.
- `/name` must be at the start of the message to run directly. Mid-sentence it only grants permission.
- Listing truncates `description` + `when_to_use` at **1,536 characters**.

### Example: research skill

`.claude/skills/market-scan/SKILL.md`

```markdown
---
name: market-scan
description: Research a market or competitor and write a sourced brief to research/. Use when asked for competitor, market, or landscape research for the pitch.
when_to_use: competitor analysis, market size, landscape, "who else does this"
argument-hint: "[company-or-market] [audience]"
allowed-tools: WebSearch WebFetch Read Write
context: fork
agent: market-researcher
background: false
---

Research: $ARGUMENTS

1. Follow the method in [method.md](method.md).
2. Cite every claim with its URL and access date.
3. Write the brief to `research/$0-market-scan.md` using [templates/brief.md](templates/brief.md).
4. Return only the file path and a five-line summary.
```

`disable-model-invocation: true` belongs on anything that publishes, sends, or deletes. For example a `/send-to-partner` skill.

---

## 2. Subagents

### Location and precedence (highest wins on name clash)

1. Managed settings
2. `--agents '<json>'` CLI flag (this session only)
3. `<repo>/.claude/agents/<name>.md` (project)
4. `~/.claude/agents/<name>.md` (all projects)
5. Plugin `agents/` directory

Identity comes from the `name` field, not the filename or subfolder.

### Frontmatter (markdown file; body is the system prompt)

| Field | Required | Type / default |
|:--|:--|:--|
| `name` | yes | string, <=256 chars, no `:` |
| `description` | yes | string; tells Claude when to delegate. Include "use proactively" to encourage automatic delegation |
| `tools` | no | comma string or YAML list; omitted = inherits all available tools |
| `disallowedTools` | no | same format; removed from the set |
| `model` | no | `sonnet`, `opus`, `haiku`, a full model ID, or `inherit` |
| `permissionMode` | no | `default`, `acceptEdits`, `auto`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | no | number; output at the limit is marked partial and resumable |
| `skills` | no | list of skill names preloaded at startup (max 32) |
| `mcpServers` | no | list of server names or inline configs |
| `memory` | no | `user`, `project`, or `local`; enables a persistent memory dir |
| `background` | no | bool; keeps it in the background |
| `effort` | no | `low`..`max` |
| `isolation` | no | `worktree` (temp git worktree; auto-cleaned if no changes) |
| `color` | no | `red`, `blue`, `green`, `yellow`, `purple`, `orange`, `pink`, `cyan` (display only) |
| `initialPrompt` | no | auto-submitted first turn when run as the main session agent |

Model resolution: per-call `model` argument > frontmatter `model` > `CLAUDE_CODE_SUBAGENT_MODEL` > main model. Built-ins: `Explore` (read-only search), `Plan`, `general-purpose`.

### Example: `.claude/agents/market-researcher.md`

```markdown
---
name: market-researcher
description: Sourced web research on markets, competitors and trends. Use proactively for any research question that needs current web sources. Writes findings to files.
tools: WebSearch, WebFetch, Read, Write, Grep, Glob
model: sonnet
color: blue
maxTurns: 40
---

You are a research analyst for a hackathon pitch.

- Every factual claim gets a URL and the date you accessed it.
- Mark unverified claims as UNVERIFIED.
- Write your full findings to the path the caller gives you, then return only the path and a summary of at most 150 words.
- Do not edit anything outside research/.
```

### How delegation works

- **Automatic:** Claude matches the task to `description`.
- **Natural language:** "Use the market-researcher subagent to ..."
- **@-mention (guaranteed):** `@"market-researcher (agent)" compare the three competitors`
- **Whole session as an agent:** `claude --agent market-researcher`, or `"agent": "market-researcher"` in `.claude/settings.json`.
- Tool name is `Agent` (renamed from `Task` in v2.1.63; `Task(...)` still works). `Agent(worker, researcher)` in `tools:` restricts which types an agent can spawn.
- A subagent gets its own context window and returns only a summary to the main conversation.

### Parallel and background

- **Foreground** subagents block the main conversation; permission prompts pass through.
- **Background** subagents run concurrently while you keep working. A background permission prompt shows in the main session labeled with the subagent's name.
- Subagents spawned from the main conversation start in the background by default. Set `CLAUDE_CODE_FORK_SUBAGENT=0` to make Claude wait for results. Press **Ctrl+B** to move a running task to the background.
- Background results come back as a completion notification in a later turn.
- Concurrency cap: 20 by default; `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` changes it. No cap on total subagents per session.
- Nesting: subagents may spawn subagents up to three levels by default (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`). Set `1` to disable nesting. Omit `Agent` from `tools` to stop one agent spawning.
- The docs do not document a `run_in_background` parameter. Use the `background` field and Ctrl+B.

Practical pattern for parallel research: ask the lead to "spawn three market-researcher subagents in parallel, one per competitor, each writing to research/<name>.md", then ask for a synthesis once they report.

---

## 3. AGENTS.md and `.agents/`

**Supported (as documented):**

- Claude Code reads `AGENTS.md` directly, starting in v2.1.277. It loads `AGENTS.md` (and `.claude/AGENTS.md`) from the working directory and its parents **only when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the working directory or above**. A `~/.claude/CLAUDE.md` and `.claude/rules/` do not count toward that check.
- If a `CLAUDE.md` exists, it wins. To keep one shared file, put `@AGENTS.md` as the first line of a `CLAUDE.md`, then add Claude-specific lines below it.
- Setting "Project instructions" to `claude-md-and-agents-md` (via `/config`, or `pluginConfigs` entry `cc-plugin-agents-md@builtin` in user settings) loads both.
- Before v2.1.281 some sessions (Bedrock, telemetry disabled) read CLAUDE.md only. Use the `@AGENTS.md` import there.
- Symlink `ln -s AGENTS.md CLAUDE.md` also works on Linux/macOS, but Edit/Write refuse to write through it. Windows clones break it. Prefer the import.
- `/import` copies instruction files from other coding agents into CLAUDE.md once.

**Not supported / not documented:** a `.agents/skills/` or `.agents/` directory is not in the skills location table. Skills must live in `.claude/skills/`. Claude Code also does not read `.cursor/rules` or `.windsurfrules` by default (only with `CLAUDE_CODE_NEW_INIT=1` does `/init` consider them).

---

## 4. Project CLAUDE.md and settings

### CLAUDE.md

| File | Scope |
|:--|:--|
| `~/.claude/CLAUDE.md` | You, all projects (your global file loads here) |
| `./CLAUDE.md` or `./.claude/CLAUDE.md` | Team, committed |
| `./CLAUDE.local.md` | You, this project; gitignore it |
| `~/.claude/rules/*.md`, `.claude/rules/*.md` | Topic files; `paths:` frontmatter scopes them |

Files from the filesystem root down to the working directory are concatenated, not overridden. Subdirectory CLAUDE.md files load on demand. Target under **200 lines**. Imports: `@path/to/file.md`, max four hops, not inside code spans or fences.

Example `CLAUDE.md` for this pitch project:

```markdown
# Pitch project (Hour49 hackathon, no coding)

## Layout
- research/   sourced briefs, one file per topic (written by subagents)
- drafts/     pitch copy and slide outlines (markdown)
- sources/    raw exports the user drops in; never edit

## Rules
- Every factual claim cites a URL with access date. Unsourced claims are marked UNVERIFIED.
- Final copy goes to drafts/; never overwrite a file in drafts/ without asking.
- Brand voice: plain, specific, no superlatives. Numbers rounded and sourced.

## Workflow
- Research: /market-scan <topic>, then synthesis in drafts/.
- Pitch sections are written in drafts/pitch-<section>.md.

@~/.claude/pitch-brand.md
```

Auto memory is on by default: `~/.claude/projects/<project>/memory/MEMORY.md` (first 200 lines or 25KB load each session). Turn off with `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1` or the `/memory` toggle.

CLAUDE.md is context, not enforcement. Use a PreToolUse hook for anything that must never happen.

### Settings files

| Scope | File | Commit? |
|:--|:--|:--|
| Managed | managed-settings.json or MDM | n/a |
| Command line | `--settings '<json>'` (one session) | n/a |
| Project local | `.claude/settings.local.json` | no (auto-added to global gitignore) |
| Shared project | `.claude/settings.json` | yes |
| User | `~/.claude/settings.json` | no |

Precedence: managed > command line > local > shared project > user. **Lists merge** (`permissions.allow` from all files combine). `allow` rules from the shared file apply only after the teammate trusts the folder; `deny` and `ask` apply immediately.

### Permissions for web research

Rule evaluation order is **deny, then ask, then allow**. A deny always wins, and an allow cannot carve an exception out of it.

Example `.claude/settings.json` for research/writing:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "WebSearch",
      "WebFetch(domain:*.gov)",
      "WebFetch(domain:crunchbase.com)",
      "WebFetch(domain:*.crunchbase.com)",
      "Read",
      "Edit(research/**)",
      "Edit(drafts/**)",
      "Write(research/**)",
      "Write(drafts/**)"
    ],
    "deny": [
      "Read(./sources/private/**)",
      "Bash",
      "WebFetch(domain:*)"
    ]
  },
  "outputStyle": "Concise"
}
```

Notes on that file:

- `WebSearch` is a bare tool name (the docs show no domain form for it). Allow it to stop prompts. Use "Yes, and don't ask again" to save it to `settings.local.json` instead.
- `WebFetch(domain:example.com)` covers that host only. Add `*.example.com` for subdomains. `WebFetch(domain:*)` matches everything.
- `WebFetch(domain:*)` as a deny blocks every fetch. Use it deliberately, not as an allow-list fallback. Remember that `deny` takes precedence over `allow`.
- `defaultMode` values: `default` (Manual), `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`. `auto` and `bypassPermissions` are ignored in project/local files. Set them in user settings or pass `--permission-mode`.
- `Edit(research/**)` in allow is anchored to the project root. `Edit(**/research/**)` matches at any depth.
- A deny on `Bash` removes the tool from Claude's context entirely. Use it only if you do not want shell access at all, which suits a non-coding lead.
- Bash rules are prefix matches and are not a security boundary. For a non-coder, denying `Bash` is the simplest safe choice.

Other keys relevant here: `model` (set `/model` default), `env`, `outputStyle`, `autoMemoryEnabled`, `claudeMdExcludes`, `permissions.additionalDirectories` (grants file access to extra folders, e.g. a shared Drive export).

### Output styles

- Switch: `/output-style Concise` (case-insensitive), or `/config` > Output style, or `"outputStyle": "Concise"` in settings. Settings values are **case-sensitive**: `Proactive`, `Concise`, `Explanatory`, `Learning`. A wrong value falls back to Default.
- Custom style file: `~/.claude/output-styles/<name>.md` (all projects) or `.claude/output-styles/<name>.md` (this project). Frontmatter: `name`, `description`, `keep-coding-instructions` (default `false`). Set it to `false` for a non-coding persona so the software-engineering instructions are dropped.

Example `.claude/output-styles/pitch-writer.md`:

```markdown
---
name: Pitch writer
description: Plain, specific, sourced writing for pitches and marketing copy
keep-coding-instructions: false
---

You write for a hackathon judge audience: 5 minutes, no jargon.

- Lead with the one-sentence claim, then the evidence.
- Every number has a source in brackets, e.g. [Source, 2026].
- Cut adjectives that do not carry a fact.
- When you are unsure, write UNVERIFIED instead of guessing.
```

Output styles are instructions, not enforcement. Restart Claude Code after editing a style file in a running session.

---

## 5. Best practices

**Keep skills small and progressive.** SKILL.md is the index, under 500 lines. Put rubrics, templates and examples in sibling files and link them. Only the description sits in context until a skill is invoked. Scripts run without loading their source.

**Write descriptions that trigger reliably.**
- Lead with the verb and the artifact: "Research a market and write a sourced brief to research/".
- Add `when_to_use` with the actual phrases a user says ("competitor", "who else does this").
- Keep it under 1,536 characters combined; the rest is truncated.
- Use `disable-model-invocation: true` for anything with side effects, so it never auto-fires.
- Test by asking the question without the slash command and checking whether it fires. If not, add trigger phrases; if it fires too often, narrow the description.

**One job per agent.** Give each subagent a narrow description, a short tool list (research agents get WebSearch, WebFetch, Read, Write; no Bash), and a fixed output path.

**Pass outputs through files, not chat.** Each subagent writes to `research/<slug>.md` and returns only the path and a summary. The lead then reads files it needs. This keeps the main context small and lets you audit sources. Name conventions in CLAUDE.md so every agent writes where the next one looks.

**Keep CLAUDE.md short and factual.** Layout, rules, and the workflow order. Move multi-step procedures into skills and part-of-codebase rules into `.claude/rules/` with `paths:`. Review it periodically for contradictions.

**Use settings for what must hold; CLAUDE.md for what should.** Deny rules and hooks enforce; CLAUDE.md and output styles guide.

**Verify your setup.** Run `/memory` to see which CLAUDE.md files loaded, `/status` for settings sources, `/permissions` for rules, and `claude doctor` for broken files. Use `/skill-doctor` to see which skills and plugins are used and what they cost in context.

**Keep the toolkit local and small.** Start with one CLAUDE.md, two skills (`market-scan`, `pitch-section`), one subagent (`market-researcher`), one output style, and the settings file. Add more only after a real task needs them.

---

## Quick file map for the junction-pitch folder

> Note (2026-11-10): superseded — the real layout is in ../README.md and the built toolkit is in ../.claude/. Kept for reference.

```text
pitch/
├── CLAUDE.md                         shared rules and layout (commit)
├── CLAUDE.local.md                   your personal notes (gitignore)
├── .claude/
│   ├── settings.json                 permissions, outputStyle (commit)
│   ├── settings.local.json           your approvals (gitignored)
│   ├── skills/market-scan/SKILL.md
│   ├── skills/pitch-section/SKILL.md
│   ├── agents/market-researcher.md
│   └── output-styles/pitch-writer.md
├── research/                         subagent output
├── drafts/                           pitch copy
└── sources/                          raw input, read-only
```

Source URLs used: https://code.claude.com/docs/en/skills.md , https://code.claude.com/docs/en/sub-agents.md , https://code.claude.com/docs/en/memory.md , https://code.claude.com/docs/en/permissions.md , https://code.claude.com/docs/en/settings.md , https://code.claude.com/docs/en/output-styles.md , https://code.claude.com/docs/en/settings-reference.md
