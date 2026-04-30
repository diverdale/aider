# Aider UI Improvements Roadmap

## Goal

Make the TUI feel more premium, more controllable, and easier to trust under heavy daily usage.

## Prioritization Framework

- Impact: user-visible value and adoption lift
- Effort: implementation complexity and risk
- Horizon:
  - Quick wins: 1-2 weeks
  - Sprint projects: 2-4 weeks
  - Strategic bets: 1-2 quarters

## Quick Wins (1-2 weeks)

### 1) Density Modes (Compact / Comfortable / Focus)
- Impact: High
- Effort: Medium
- Why:
  - Different users need different information density and spacing.
  - Focus mode reduces visual noise during long edit/apply cycles.
- Implementation:
  - Add `ui-density` setting with 3 presets.
  - Tune padding/margins, line spacing, and panel collapse defaults.
  - Add keybinding to cycle density modes.
- Success metrics:
  - Higher session duration without abandonment.
  - Fewer manual toggles to hide/show panes.

### 2) Contextual Key Hints Bar
- Impact: High
- Effort: Low
- Why:
  - Improves discoverability without requiring docs lookup.
- Implementation:
  - Render a bottom hint bar based on active panel/state.
  - Hide advanced hints unless user presses a help key.
- Success metrics:
  - Increased shortcut usage.
  - Reduced command typo/help-command frequency.

### 3) Better Progress States (Now / Next / Waiting On)
- Impact: High
- Effort: Medium
- Why:
  - Users trust the system when they know what is happening and why.
- Implementation:
  - Add progress labels for scan, plan, edit, test, summarize.
  - Include short reason text for each state transition.
- Success metrics:
  - Lower interruption/cancel rate mid-run.
  - Better user-reported confidence.

### 4) Diff Legibility Upgrade
- Impact: Medium-High
- Effort: Medium
- Why:
  - Review quality drives acceptance rates.
- Implementation:
  - Improve color contrast and intraline change highlighting.
  - Add optional symbol-level highlight for renamed variables.
- Success metrics:
  - Faster diff review completion.
  - Higher apply/accept ratio.

## Sprint Projects (2-4 weeks)

### 5) Layout Presets (Single, Split, Review-First)
- Impact: High
- Effort: Medium-High
- Why:
  - Stable task-specific layouts reduce cognitive load.
- Implementation:
  - Add `ui-layout` presets with keyboard switching.
  - Persist per-repo or global preference.
- Success metrics:
  - Fewer panel toggles per session.
  - Improved usability survey scores.

### 6) Command Palette and Fuzzy Action Search
- Impact: High
- Effort: Medium
- Why:
  - Lets users discover and run actions quickly without memorization.
- Implementation:
  - Add a palette modal with fuzzy matching for commands, skills, themes, recent actions.
  - Include “recent and pinned” actions.
- Success metrics:
  - Faster command execution time.
  - Increased usage of non-obvious features (skills, themes, diagnostics).

### 7) Approval Workflow Polish
- Impact: High
- Effort: Medium
- Why:
  - Control and reversibility are key for trust.
- Implementation:
  - Add one-key actions: approve hunk, skip file, revert last action.
  - Show explicit undo labels (what was reverted).
- Success metrics:
  - More accepted changes per session.
  - Fewer hard aborts and manual git resets.

### 8) First-Run Health Check
- Impact: Medium-High
- Effort: Medium
- Why:
  - Smooth onboarding reduces setup drop-off.
- Implementation:
  - Add startup checks for API keys, model/provider availability, git hooks, and theme validity.
  - Provide actionable auto-fix suggestions.
- Success metrics:
  - Reduced support issues for setup/config.
  - Faster time-to-first-successful-run.

## Strategic Bets (1-2 quarters)

### 9) Session Timeline and Replay
- Impact: Very High
- Effort: High
- Why:
  - Makes assistant behavior auditable and teachable.
- Implementation:
  - Timeline of prompt, tool calls, edits, tests, outcomes.
  - Click any step to inspect details and optionally replay.
- Success metrics:
  - Faster debugging of failed sessions.
  - Better team collaboration on prompt/workflow tuning.

### 10) Persona Profiles (Reviewer / Builder / Refactorer / Hotfix)
- Impact: High
- Effort: High
- Why:
  - Tailors behavior, verbosity, and risk profile per task mode.
- Implementation:
  - Add `ui-persona` and behavior bundles (tone, detail, confirmation strictness).
  - Ship opinionated defaults with easy customization.
- Success metrics:
  - Higher repeat usage across different task types.
  - Lower configuration churn per session.

### 11) Team Policy Mode in UI
- Impact: Very High (team/enterprise)
- Effort: High
- Why:
  - Makes constraints visible and enforceable during interactive workflows.
- Implementation:
  - Display active policies in sidebar (tests required, prohibited paths, risk thresholds).
  - Block or warn before policy-violating actions.
- Success metrics:
  - Lower policy violations.
  - Higher enterprise confidence/adoption.

## Recommended Execution Order

1. Density modes + key hints + progress states
2. Diff legibility + approval workflow polish
3. Layout presets + command palette
4. First-run health check
5. Session timeline
6. Persona profiles and policy mode

## Design Principles

- Clarity over decoration
- Fast keyboard-first interactions
- Reversible actions with clear audit trail
- Discoverability without clutter
- User control over automation depth

## Suggested Initial Milestone (4 weeks)

- Week 1:
  - Density modes
  - Key hints bar
- Week 2:
  - Progress state labels and transitions
  - Diff contrast/intraline improvements
- Week 3:
  - Approval quick actions and undo labeling
- Week 4:
  - Layout presets (first version)
  - Telemetry and feedback pass

## Telemetry and Validation

Track before/after metrics to validate value:

- Time from prompt to accepted change
- Number of manual UI toggles per session
- Abort/cancel rate mid-run
- Percentage of runs ending with successful apply + tests
- Feature adoption rates (palette, profiles, skills, themes)
