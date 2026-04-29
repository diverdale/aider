# PR Description

## Summary

This PR adds a full skills system to aider and upgrades CLI theming so users can apply presets/custom themes while keeping explicit per-color overrides.

It also makes explicit `--config` usage isolated from default config discovery to avoid surprising merge behavior.

## Why

- Enable reusable SKILL.md-based workflows with both auto-apply and explicit invocation.
- Improve terminal UX consistency (spinner, divider, output colors) under configurable themes.
- Make config behavior more predictable for local debugging and reproducible runs.

## What Changed

### Skills system

- Added `SkillsManager` and `Skill` metadata model.
- Added tolerant frontmatter parsing (supports preamble text before YAML block).
- Added trigger-based matching plus single-trigger fallback for action-like requests.
- Added install/update/remove/enable/disable/refresh support.
- Added source tracking via `.source` for update workflows.

### Command integration

- Added `/skills` management commands:
  - `list`, `refresh`, `info/show`, `add/load`, `remove`, `enable`, `disable`, `update`
- Added dynamic command fallback for `/skill-name`.
- Added automatic skill preprocessing for non-command user prompts.

### Prompt/coder integration

- Wired skills context into system prompt assembly.
- Wired skill auto-apply path into normal user input preprocessing.

### Theme and output improvements

- Added `--color-theme` and `--rule-color` options.
- Added theme preset map + custom theme-file loading.
- Added `color-theme: list/help/?` behavior.
- Added override precedence logic so explicit color settings still win.
- Added `rule_color` to decouple divider color from user-input color.
- Updated spinner implementation and connected spinner color to assistant output color.

### Config loading behavior

- Changed startup behavior so explicit `--config` runs in isolated mode (does not also discover/merge default config files).

### Tests

- Expanded command tests for skills preprocessing and `/skills` load behavior.
- Added dedicated skills tests (frontmatter parsing, install paths, GitHub tree URL translation, fallback matching).

## User-Visible Changes

- Users can quickly apply bundled color presets (including light presets) or custom theme files.
- Users can still override specific colors individually after selecting a theme.
- Spinner and divider visuals now reflect configured theme values more consistently.
- Skills can auto-activate from prompt intent, not only via explicit slash commands.

## Example Config

```yaml
# Preset + local overrides
color-theme: iterm-dark
assistant-output-color: "#ff8800"
rule-color: "#7aa2f7"
code-theme: github-dark
```

```yaml
# Custom theme file + explicit override
color-theme: /home/user/.aider/themes/my-theme.yml
assistant-output-color: "#ffaa00"
```

```yaml
# Theme file content
colors:
  user-input-color: "#e6edf3"
  rule-color: "#7aa2f7"
  tool-output-color: "#9ece6a"
  tool-warning-color: "#e0af68"
  tool-error-color: "#f7768e"
  assistant-output-color: "#7aa2f7"
  code-theme: monokai
```

## Validation

- Targeted skills/commands tests passed repeatedly during development.
- No static errors reported in key touched files during latest diagnostics.

## Risks / Reviewer Notes

- Skills manager lifecycle appears in both command and coder paths; verify there is no duplicate state or unnecessary rescans.
- Auto-skill prompt wrapping increases prompt size; monitor behavior on small local models.
- `safe_add` utility addition may be unrelated to this scope and could be split if needed.

## Migration / Compatibility Notes

- Users relying on implicit config-file merging while also passing explicit `--config` may see behavior changes; explicit config now takes precedence as a standalone source.
