# Dev vs Main Deep-Dive Diff Report

Date: 2026-04-28
Workspace: aider
Comparison baselines:
- Committed branch delta: main...HEAD
- Effective current delta: main vs current working tree (including local modifications)

## Executive Summary

The dev branch introduces two major capabilities:
- A full skills subsystem (discovery, matching, install/update, command routing, and prompt injection)
- A color theme system upgrade (presets, custom theme files, override precedence, and spinner/rule color wiring)

It also adjusts config precedence behavior by making explicit --config usage isolated from default config discovery.

## Branch and Diff Scope

Snapshot details used for this report:
- Current branch: dev
- HEAD: 52723db6c
- main: 3ec8ec5a7
- Working tree: dirty (tracked edits plus one untracked test file)

Committed-only delta (main...HEAD):
- 4 files changed
- 290 insertions
- 1 deletion

Working-tree-inclusive delta (git diff main):
- 9 tracked files modified
- 1171 insertions
- 98 deletions
- Plus untracked tests/basic/test_skills.py

## Change Inventory and Purpose

### 1) New skills subsystem

File:
- aider/skills.py

What changed:
- Added Skill dataclass including source_url metadata
- Added tolerant frontmatter parser that can parse YAML frontmatter after prose preambles
- Added trigger-based matching and a fallback action-intent matcher
- Added compact skills context generation for prompt injection
- Added lifecycle operations: list, remove, toggle enable/disable, update, install
- Added local path and URL/GitHub install logic with persisted .source for updates

Purpose:
- Introduces Claude Code style SKILL.md support in aider
- Enables both automatic and explicit skill usage
- Makes skills manageable and updateable over time

Behavioral impact:
- Skills can now influence normal chat requests via trigger matching
- Skill metadata parsing is more robust for hand-authored files

### 2) Command integration for skills

File:
- aider/commands.py

What changed:
- Added _run_skill helper
- Added _auto_apply_relevant_skills preprocessing helper
- Added cmd_skills management command family (list, refresh, info, add/load, remove, enable, disable, update)
- Added dynamic fallback so /skill-name works as command invocation

Purpose:
- Turns skills into a first-class command UX
- Preserves direct /skill-name invocation while enabling automatic use

Behavioral impact:
- User can manage skills without editing files manually
- Non-command user prompts can be skill-enriched before model execution

### 3) Coder pipeline wiring

File:
- aider/coders/base_coder.py

What changed:
- Initializes SkillsManager in coder flow
- Invokes command-side auto-skill preprocessing for non-command user input
- Injects compact skills context into system prompt construction
- Passes assistant output color into WaitingSpinner

Purpose:
- Integrates skills into core orchestration, not just a side command
- Aligns spinner visuals with configured assistant color

Behavioral impact:
- Skills become part of prompt lifecycle automatically
- Spinner adopts user-defined output color preferences

### 4) Spinner rewrite and color model

File:
- aider/waiting.py

What changed:
- Reworked spinner animation model with fade frames
- Added color parsing and stepped color blending logic
- Added color parameter support to WaitingSpinner constructor

Purpose:
- Improve waiting/streaming UX readability and perceived responsiveness
- Respect user color configuration

Behavioral impact:
- Spinner visual style is richer and no longer hardcoded in one color path

### 5) IO rule color decoupling

File:
- aider/io.py

What changed:
- Added rule_color as a first-class output color setting
- Added validation/path handling for rule_color
- rule() now prefers rule_color and falls back to user_input_color

Purpose:
- Decouples divider/rule visuals from user input text color

Behavioral impact:
- Avoids unintended full-screen single-color appearance when user_input_color is customized

### 6) New CLI/config options for themes

File:
- aider/args.py

What changed:
- Added --color-theme
- Added --rule-color

Purpose:
- Exposes theme selection and divider color control at CLI/config level

Behavioral impact:
- Users can select bundled presets or custom file-backed themes

### 7) Theme engine and config precedence in startup

File:
- aider/main.py

What changed:
- Added OUTPUT_COLOR_DEFAULTS and COLOR_THEME_PRESETS maps
- Added theme loading support from preset names or file paths
- Added key normalization and color-theme preset listing utility
- Added color-theme list/help/? handling
- Added apply_color_theme_overrides to preserve explicit individual color settings
- Added explicit --config isolation behavior from default config file discovery
- Added rule_color handoff into InputOutput construction

Purpose:
- Centralize and formalize theme behavior
- Make explicit config mode deterministic and easier to reason about

Behavioral impact:
- Theme presets can quickly style the CLI while preserving specific user overrides
- --config now behaves as an explicit source, reducing hidden merge surprises

### 8) Tests added or expanded

Files:
- tests/basic/test_commands.py
- tests/basic/test_skills.py (untracked at capture time)

What changed:
- Added tests for preprocess auto-skill behavior and /skills load flow
- Added broader skills tests for:
  - frontmatter parsing after preamble
  - local path installs
  - GitHub tree URL translation
  - fallback matching behavior

Purpose:
- Lock in skills parsing/routing/installer behavior
- Reduce regression risk for command integration paths

### 9) Miscellaneous utility addition

File:
- aider/utils.py

What changed:
- Added safe_add helper

Purpose:
- Not clearly tied to skills/theme initiative based on current branch scope

Note:
- Candidate for separate review to confirm intent and scope fit

## Config and Theme Examples

### A) Preset usage with targeted overrides

    color-theme: iterm-dark
    assistant-output-color: "#ff8800"
    rule-color: "#7aa2f7"
    code-theme: github-dark

### B) Full manual color setup

    dark-mode: true
    assistant-output-color: "#7aa2f7"
    user-input-color: "#c0caf5"
    rule-color: "#7aa2f7"
    tool-output-color: "#9ece6a"
    tool-warning-color: "#e0af68"
    tool-error-color: "#f7768e"
    completion-menu-color: "#c0caf5"
    completion-menu-bg-color: "#1f2335"
    completion-menu-current-color: "#1f2335"
    completion-menu-current-bg-color: "#7aa2f7"
    code-theme: monokai

### C) Custom theme file plus local override

Main config:

    color-theme: /home/dale/.aider/themes/my-theme.yml
    assistant-output-color: "#ffaa00"

Theme file:

    colors:
      user-input-color: "#e6edf3"
      rule-color: "#7aa2f7"
      tool-output-color: "#9ece6a"
      tool-warning-color: "#e0af68"
      tool-error-color: "#f7768e"
      assistant-output-color: "#7aa2f7"
      code-theme: monokai

### D) Preset listing helper usage

    color-theme: list

or via CLI:

    aider --color-theme list

## Risks, Review Notes, and Follow-ups

- Skills manager lifecycle now appears in both command and coder pathways; worth confirming there is no duplicate state or unnecessary rescans.
- Auto-skill prompt wrapping increases prompt size; test impact on small local models and context budgets.
- safe_add in utils may be unrelated to this change set and might be better isolated in a dedicated commit if not required.

## PR-Ready Condensed Changelog

Use this section directly in a pull request description.

### Highlights

- Added a new SKILL.md-compatible skills subsystem with discovery, metadata parsing, trigger matching, install/update, and enable/disable support.
- Integrated skills into both command routing and normal prompt preprocessing.
- Added /skills management commands and /skill-name dynamic invocation fallback.
- Reworked waiting spinner rendering and wired spinner color to assistant output theme settings.
- Introduced comprehensive color-theme support with built-in presets, custom theme files, and explicit per-color override precedence.
- Added new --rule-color setting to decouple divider line color from user input color.
- Updated config loading semantics so explicit --config runs in isolated mode instead of implicit config-file merging.
- Expanded tests around skills parsing, installation, matching, and command integration paths.

### User-visible behavior changes

- Themes can be set quickly via presets (including new light presets) or custom files.
- Individual color options still override theme defaults.
- Spinner and divider visuals now track theme settings more predictably.
- Skills can be auto-applied based on request intent, not only via explicit commands.

### Validation snapshot

- Targeted tests repeatedly passed during development for skills and commands flows.
- No static errors reported in key touched files during latest diagnostics.
