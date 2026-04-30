# UI Improvements Backlog (Issue Ready)

This backlog turns the roadmap into concrete build tickets with acceptance criteria.

## P0-1: UI Density Modes

- Title: Add UI density modes (compact, comfortable, focus)
- Status: Started
- Scope:
  - Add config option `ui-density`
  - Apply density to prompt chrome and file context display
- Acceptance criteria:
  - `--ui-density compact|comfortable|focus` is accepted by CLI/config
  - Focus mode shows a compact context summary instead of full file lists
  - Compact mode reduces prompt completion menu reserve space
  - Invalid density values produce a clear error
- Notes:
  - Initial implementation completed in this branch

## P0-2: Contextual Key Hints Bar

- Title: Add dynamic key hints based on active prompt state
- Status: Completed
- Scope:
  - Show key hints for submit/newline/edit-in-editor/history navigation
  - Keep hints concise and context-aware
- Acceptance criteria:
  - Hint bar appears during input prompts
  - Hints change correctly when multiline mode toggles
  - Hint bar can be disabled via config

## P0-3: Progress State Strip

- Title: Add "Now / Next / Waiting on" progress strip
- Status: In progress
- Scope:
  - Show active stage (scan, plan, edit, test, summarize)
  - Show one-line reason for current stage
- Acceptance criteria:
  - Every major stage transition updates strip text
  - Strip does not spam output logs
  - Works in both pretty and non-pretty modes

## P1-1: Review-First Layout Preset

- Title: Introduce layout presets (single, split, review-first)
- Status: In progress
- Scope:
  - Add layout preset setting
  - Keep defaults backward-compatible
- Acceptance criteria:
  - Preset can be selected via config and command
  - Review-first emphasizes changed files and diffs
- Notes:
  - Initial split layout behavior shipped: grouped context header, split hint cue, and split progress label.

## P1-2: Command Palette

- Title: Fuzzy command/action palette
- Status: In progress
- Scope:
  - Search commands, skills, theme actions
  - Include recent actions
- Acceptance criteria:
  - Palette opens via shortcut
  - Selecting an item executes mapped action
  - Results ranked by exact + fuzzy relevance
- Notes:
  - Initial slash-command palette shipped via /palette with fuzzy ranking, recent action boost, and number-based execution.
  - Added Ctrl-P shortcut to open the palette from the input prompt.
  - Added immediate number prompt after palette listings for one-flow selection and execution.

## P1-3: Approval UX Shortcuts

- Title: One-key approve/skip/revert controls
- Status: Completed
- Scope:
  - Add explicit quick actions in review flow
  - Add labeled undo information
- Acceptance criteria:
  - User can approve/skip/revert with single keys
  - Undo action surfaces what was reverted

## P1-4: First-Run Health Check

- Title: Add startup diagnostics for setup confidence
- Status: In progress
- Scope:
  - Check API key presence, model/provider reachability, git hooks
  - Offer actionable guidance
- Acceptance criteria:
  - Health check runs on demand and optional first launch
  - Failures provide clear fix commands
- Notes:
  - Initial on-demand command shipped: /health (with optional --quick).
  - First slice includes API key presence, model reachability probe, and git readiness checks.

## P2-1: Session Timeline

- Title: Build session timeline with replay points
- Scope:
  - Record major events: prompt, tool call, edit, test, result
- Acceptance criteria:
  - Timeline entries are chronological and inspectable
  - User can jump to event details in current session

## P2-2: Persona Profiles

- Title: Add UI behavior profiles (reviewer, builder, refactorer, hotfix)
- Scope:
  - Bundle verbosity/confirmation defaults by persona
- Acceptance criteria:
  - Persona can be set via config/command
  - Persona changes are reflected immediately

## P2-3: Team Policy Display

- Title: Surface active policy constraints in UI
- Scope:
  - Show active policy rules and warnings before risky actions
- Acceptance criteria:
  - Policy panel clearly lists active constraints
  - Blocking and warning behavior is deterministic

## Suggested Delivery Sequence

1. P0-1 UI density modes
2. P0-2 key hints bar
3. P0-3 progress strip
4. P1-3 approval UX shortcuts
5. P1-1 layout presets
6. P1-2 command palette
