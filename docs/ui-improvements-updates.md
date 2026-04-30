# UI Improvements Updates and Usage

This file tracks what has been shipped so far and how to use each feature.

## Update 1: UI Density Modes

Status: Shipped

What changed:
- Added ui-density with values: compact, comfortable, focus.
- Focus mode collapses file context listing to a summary line.
- Compact mode reduces completion menu reserve space.

How to use:
- CLI examples:
  - aider --ui-density compact
  - aider --ui-density comfortable
  - aider --ui-density focus
- Config example:
  - ui-density: focus

## Update 2: Contextual Key Hints Bar

Status: Shipped

What changed:
- Added toggle for prompt footer key hints.
- Hints adapt to normal or multiline mode.

How to use:
- CLI:
  - aider --ui-key-hints
  - aider --no-ui-key-hints
- Config:
  - ui-key-hints: true

## Update 3: Custom Hint Template with Model and Context Fields

Status: Shipped

What changed:
- Added customizable hint template placeholders:
  - {mode}
  - {density}
  - {model}
  - {context_used}
  - {context_max}
  - {context_pct}
- Default hint now shows context as percentage.

How to use:
- CLI:
  - aider --ui-key-hints-template "{model} | ctx {context_pct} | {mode}"
- Config:
  - ui-key-hints-template: "{model} | ctx {context_pct} | {mode}"

## Update 4: Progress Strip (Now / Next / Waiting)

Status: In progress

What changed:
- Added progress state support in the prompt footer.
- Added settings:
  - ui-progress-strip
  - ui-progress-template
- Progress status updates during message lifecycle.

How to use:
- CLI:
  - aider --ui-progress-strip
  - aider --no-ui-progress-strip
  - aider --ui-progress-template "Now:{now} Next:{next} Waiting:{waiting_on}"
- Config:
  - ui-progress-strip: true
  - ui-progress-template: "Now:{now} Next:{next} Waiting:{waiting_on}"

## Update 5: Approval Shortcut for Undo

Status: Shipped

What changed:
- Added one-key undo action to confirmation prompts that support rollback.
- Lint and test follow-up prompts now include an Undo option when in a git repo.

How to use:
- When prompted with:
  - Attempt to fix lint errors?
  - Attempt to fix test errors?
- Press U to trigger undo of the last aider commit and skip the current fix attempt.

Expanded one-key approval mappings:
- Create new file prompt:
  - C = Create
  - S = Skip
- Allow edits to non-chat file prompt:
  - A = Approve
  - S = Skip
  - U = Undo last aider commit (when available)
- Lint/test follow-up prompts:
  - F = Fix
  - S = Skip
  - U = Undo last aider commit (when available)
- Shell command approval prompt:
  - R = Run
  - S = Skip

## Update 6: UI Layout Presets (Initial)

Status: In progress

What changed:
- Added ui-layout preset setting with:
  - single
  - split
  - review-first
- Review-first currently adds review workflow guidance in the file context block.
- Non-single layouts are reflected in default key hints.

How to use:
- CLI:
  - aider --ui-layout single
  - aider --ui-layout split
  - aider --ui-layout review-first
- Config:
  - ui-layout: review-first

## Update 7: Review-First Hints and Progress Refinement

Status: In progress

What changed:
- Review-first key hints now explicitly include:
  - /diff review
  - /undo revert
- Default progress strip in review-first now includes quick reminder fields:
  - Review:/diff
  - Undo:/undo
- Message lifecycle progress wording is more review-oriented during response and apply phases.

How to use:
- CLI:
  - aider --ui-layout review-first
- Optional custom progress template still overrides defaults:
  - aider --ui-progress-template "Now:{now} Next:{next} Waiting:{waiting_on}"

## Update 8: Split Layout Behavior (Initial)

Status: In progress

What changed:
- Split layout now adds explicit context header text indicating grouped readonly/editable files.
- Default key hints in split layout include a compact split reminder.
- Default progress strip in split layout includes `Layout:split` for quick mode visibility.

How to use:
- CLI:
  - aider --ui-layout split
- Config:
  - ui-layout: split

## Update 9: Command Palette (Initial)

Status: In progress

What changed:
- Added /palette command for fuzzy action search.
- Added Ctrl-P keyboard shortcut to open palette directly from the prompt.
- Added immediate selection prompt after listing matches.
- Palette searches:
  - slash commands
  - enabled skills
  - theme-related help actions
- Ranking combines exact/prefix/contains and fuzzy match quality.
- Recent actions are boosted when no query is provided.
- Number-based selection executes the chosen action.

How to use:
- Open palette from prompt:
  - Ctrl-P
- Show ranked actions for a query:
  - /palette tok
- Show recent/default ranked actions:
  - /palette
- Execute a listed item:
  - /palette 1
- Choose immediately after listing:
  - type a number when prompted

## Update 10: First-Run Healthcheck (Initial)

Status: In progress

What changed:
- Added /health command for setup diagnostics.
- Checks currently include:
  - API key presence for active model
  - model/provider connectivity probe
  - git readiness
- Output includes per-check status and actionable fix text.

How to use:
- Full checks:
  - /health
- Fast checks without network probe:
  - /health --quick

## Update 11: Session Accept-All for File Prompts

Status: Shipped

What changed:
- Added session-level toggle to auto-accept repetitive file prompts during scaffolding.
- Covers both:
  - Create new file?
  - Allow edits to file not yet added to chat?

How to use:
- Enable for current session:
  - /accept-all
  - /accept-all on
- Check state:
  - /accept-all status
- Disable and restore prompts:
  - /accept-all off

## Combined Example

ui-density: compact
ui-key-hints: true
ui-key-hints-template: "{model} | ctx {context_pct} | {mode}"
ui-progress-strip: true
ui-progress-template: "Now:{now} Next:{next} Waiting:{waiting_on}"
