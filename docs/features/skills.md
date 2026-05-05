# Skills — Reusable, Shareable Prompt Modules

A skill is a `SKILL.md` file with YAML frontmatter that describes a reusable behavior the model should adopt for certain kinds of requests. The format is **compatible with Claude Code's skills**, so skills written for one tool work in the other unchanged.

The classic use case: you want the model to follow your team's commit-message conventions, your codebase's testing patterns, or your preferred refactoring style — without retyping that context every session. Drop a `SKILL.md` in `~/.aider/skills/<name>/`, and aider will inject it into the prompt when it detects the user's request matches the skill's triggers.

---

## Quick start

### Install a skill from GitHub

```
/skills add https://github.com/some-user/some-repo
```

This downloads `SKILL.md` from the repo's default branch into `~/.aider/skills/<skill-name>/`. Bare repo URLs, `/blob/<branch>/path/SKILL.md` URLs, `/tree/<branch>/path/` URLs, and raw `raw.githubusercontent.com` URLs all work.

### Install from a local path

```
/skills add ~/my-skills/refactor-imports
```

Copies the local skill directory into `~/.aider/skills/`. Use this for skills you write yourself or share via a directory you sync.

### Verify it loaded

```
/skills list
```

Shows installed skills with their description, location (global vs project), and enabled state.

### Use it

If the skill defines triggers (see below), aider auto-applies it whenever a user message contains one of the triggers. Otherwise, prefix the user message with `/<skill-name>` to invoke it explicitly.

---

## SKILL.md format

```markdown
---
name: refactor-python-imports
description: Reorganize and prune Python imports across a project.
version: 0.3.1
triggers:
  - reorganize imports
  - prune imports
  - sort imports
---

# Refactor Python imports

You are an expert at reorganizing Python imports per PEP 8...

(rest of the body — the model sees this verbatim when the skill is applied)
```

### Frontmatter fields

| Field | Required | Notes |
|---|---|---|
| `name` | Sort of | Falls back to the parent directory name (lowercased, spaces → dashes) if omitted. Used as the install handle and `/skill-name` invocation. |
| `description` | No (defaults to "No description provided.") | Shown in `/skills list` and used to build the compact context aider injects when the skill applies. Keep it under ~200 chars. |
| `version` | No (defaults to `1.0`) | Free-form string. |
| `triggers` | No (defaults to `[]`) | List of strings. If any trigger appears as a substring of the user's message (case-insensitive), the skill auto-applies. **No triggers = the skill is reference-only**, invokable by `/skill-name` but never auto. |

### Body

Everything after the `---` block is the **skill body** — markdown that the model reads as instructions when the skill applies. Treat it like a system-prompt addition: clear, scoped, and short. Long bodies eat your context budget.

The frontmatter parser tolerates a prose preamble before the `---` block, so you can keep a human-readable intro at the top of the file:

```markdown
This skill helps with reorganizing Python imports.
It enforces PEP 8 grouping and uses isort with the black profile.

---
name: refactor-python-imports
...
---

# Behavior

(skill body here)
```

---

## Auto-apply via triggers

When the user types a message, aider scans the message against every enabled skill's triggers (lowercased substring match). The skill with the **longest matching trigger** wins. Its body is added to the prompt for that turn.

### Example

```yaml
triggers:
  - reorganize imports
  - prune imports
```

Now any user message containing "reorganize imports" or "prune imports" auto-applies this skill.

### Tie-breaking

Longer trigger wins. If two skills both match the same message, the one whose matching trigger is longer takes precedence. If still tied, the one loaded first wins (deterministic but order-dependent — keep your triggers distinct).

### Single-skill fallback

If **exactly one** enabled skill has triggers, AND the user's message looks like an action request (verbs like `refactor`, `add`, `fix`, `optimize`, etc.), that skill applies even if no specific trigger matched. This makes the practical case ("I have one workflow skill installed") work without forcing every conceivable verb into the trigger list.

If you have multiple skills installed, the fallback is disabled — auto-apply requires an explicit trigger match.

---

## Slash commands

All under `/skills`. Synonyms in parens.

### `/skills list`

Show installed skills:

```
Installed skills (3 total):
  ✓ refactor-python-imports (global) - Reorganize and prune Python imports across a project.
  ✓ commit-message-style    (project) - Use our team's conventional-commit format with scopes.
  ✗ legacy-debug            (global) - (disabled)
```

`✓` = enabled, `✗` = disabled. The location column shows whether the skill lives in the global (`~/.aider/skills/`) or project (`./.aider/skills/`) directory.

### `/skills refresh`

Re-scan both skills directories. Use this after manually adding files or editing a `SKILL.md`.

### `/skills info <name>` (alias `/skills show <name>`)

Print the full body of a skill so you can review what the model would actually see when the skill applies.

### `/skills add <url-or-path>` (alias `/skills load <url-or-path>`)

Install a skill. Three input shapes are supported:

```
/skills add ~/my-skills/refactor-imports                 # local directory
/skills add https://github.com/me/my-skills              # bare repo (looks for SKILL.md at main)
/skills add https://github.com/me/my-skills/blob/main/refactor-imports/SKILL.md
/skills add https://github.com/me/my-skills/tree/main/refactor-imports
/skills add https://raw.githubusercontent.com/me/my-skills/main/refactor-imports/SKILL.md
```

The skill ends up at `~/.aider/skills/<name>/SKILL.md`. The original URL/path is stored in `~/.aider/skills/<name>/.source` so `/skills update` can re-fetch it.

### `/skills remove <name>`

Delete the skill's directory. Cannot be undone.

### `/skills enable <name>` / `/skills disable <name>`

Toggle without deleting. Disabled skills don't auto-apply and aren't candidates for explicit invocation.

### `/skills update <name>`

Re-fetch from the stored `.source` URL. Useful when the skill author has improved their `SKILL.md`.

```
Updating skill 'refactor-python-imports'...
✓ Skill 'refactor-python-imports' updated from https://github.com/jane/aider-refactor-imports
```

Skills installed from local paths cannot be updated this way (no source URL to fetch). Re-install instead.

### `/<skill-name>` — direct invocation

Any skill name becomes a slash command. So if you've installed a skill named `commit-message-style`:

```
/commit-message-style add a fix for the SSL bypass
```

This forces the skill to apply for that turn, regardless of triggers.

---

## Directory layout

```
~/.aider/skills/                          # global, applies to every aider session
├── refactor-python-imports/
│   ├── SKILL.md
│   └── .source                           # original install URL/path
└── commit-message-style/
    └── SKILL.md

./.aider/skills/                          # project-local, this repo only
└── this-projects-conventions/
    └── SKILL.md
```

Project-local skills override global ones with the same name. Both are scanned at startup; `/skills refresh` re-scans on demand.

---

## Writing your own skills

### Minimal example

```markdown
---
name: hello-skill
description: A trivial example.
triggers:
  - say hello
---

# Hello skill

When the user asks you to say hello, respond with a short greeting in their preferred language.
```

Save as `~/.aider/skills/hello-skill/SKILL.md`. Run `aider`, then say "say hello in french" — the skill auto-applies and the model uses the body's instruction.

### Best practices

- **Keep the body short.** Every skill that applies costs tokens in the model's context. 100–300 lines is reasonable; 1000+ is rarely productive.
- **Make triggers distinctive.** "fix" matches almost any conversation; "fix lint errors" is much narrower and won't fire spuriously.
- **Test both with and without the trigger.** A user asking "I want to refactor imports" and "reorganize my imports" should both work. Add multiple trigger phrasings.
- **Pin a version in frontmatter.** When you update the body meaningfully, bump the version. `/skills list` shows it.
- **Prefer global to project-local for cross-cutting skills.** Reserve the project directory for skills genuinely specific to one repo.

### Sharing with others

Push your `SKILL.md` (and ideally a top-level README explaining it) to a public GitHub repo. Then anyone can install it with:

```
/skills add https://github.com/<you>/<repo>
```

If the skill isn't at the repo root, link to the directory or the raw `SKILL.md`:

```
/skills add https://github.com/<you>/<repo>/tree/main/skills/<name>
```

### Updating after install

If you change your skill's `SKILL.md` upstream, users can pull the change with:

```
/skills update <name>
```

This re-fetches from the original install URL — no reinstall needed.

---

## Compatibility with Claude Code

Aider's skill format is intentionally identical to Claude Code's: same YAML frontmatter, same body conventions, same auto-apply semantics. A skill you install from one works in the other.

There are two minor differences in **how aider applies them**:

1. **No skill dependency declarations.** Claude Code lets a skill declare `allowed-tools: "mcp__github__*"` to pre-approve MCP tool calls during the skill. Aider's permission gate (see [mcp.md](./mcp.md)) is independent of skills — every tool call goes through the resolver regardless of which skill triggered it. You can achieve the same effect by setting `default_permission: auto` in `mcp.yml` for the relevant server.
2. **Aider's auto-apply uses substring trigger matching.** Claude Code uses richer skill-router heuristics. The substring approach is simpler and more predictable; the trade-off is that you need to put the trigger phrase in the user's message verbatim.

---

## Related

- [mcp.md](./mcp.md) — skills can recommend (but not auto-install) MCP servers in their bodies. The two systems are independent but complementary.
- The skills runtime lives in `aider/skills.py` (`SkillsManager`); the slash commands are in `aider/commands.py::cmd_skills`. Tests in `tests/basic/test_skills.py`.
