# Color Theming

Aider's terminal output (assistant text, user input, tool output, warnings, errors, divider lines, completion menu, code-block syntax highlighting) is fully themable. This fork adds:

1. **Built-in theme presets** — pick a name like `dracula` or `solarized-light` and get a coordinated palette.
2. **Custom theme files** — drop a YAML file with your own colors.
3. **Per-color overrides** — keep a preset but tweak one or two values without writing a whole theme.
4. **A separate `rule_color`** — divider lines no longer have to share the user-input color.

---

## Quick start

### Use a preset

```bash
aider --color-theme dracula
```

Or set it once in `.aider.conf.yml`:

```yaml
color-theme: dracula
```

### List presets

```bash
aider --color-theme list   # or "?" or "help"
```

Prints the available preset names and exits.

### Use a custom theme file

```bash
aider --color-theme ~/.aider/themes/my-theme.yml
```

See [Theme file format](#theme-file-format) below.

### Override one color from a preset

```yaml
color-theme: dracula
assistant-output-color: "#ff8800"   # override just this one; rest stays dracula
```

### Use the new rule-color setting

```bash
aider --rule-color "#7aa2f7"
```

Sets the color of horizontal divider lines (between turns, around panels). Previously these tracked `user-input-color`, which made full-screen output look monotone if you customized your input color. The two are now independent.

---

## Built-in presets

Seven presets ship with the fork:

| Preset | Background expectation | Notes |
|---|---|---|
| `iterm-dark` | dark | Tokyo-night-style cool blues |
| `tokyo-night` | dark | Same as iterm-dark; alias |
| `dracula` | dark | The official Dracula palette |
| `gruvbox-dark` | dark | Warm Retro Group of Boxes™ |
| `nord` | dark | Frosted blues and whites |
| `iterm-light` | light | High-contrast indigo/violet on white |
| `solarized-light` | light | The original Solarized Light |

Each preset sets the full color set: text colors, completion menu, plus a Pygments `code_theme` for code blocks (most use `monokai`; light themes use Pygments' `default`).

---

## All settings

All can be set via CLI flag (`--<setting>`), env var (`AIDER_<SETTING>`), or `.aider.conf.yml` (`<setting>:`). Defaults shown below; `None` means "use terminal default".

| Setting | Default | What it affects |
|---|---|---|
| `user-input-color` | `#00cc00` | Your typed input + the input-prompt accents. |
| `assistant-output-color` | `#0088ff` | Streaming model text + the spinner. |
| `tool-output-color` | None | `io.tool_output(...)` lines (status, MCP `→` `←` lines, etc.). |
| `tool-warning-color` | `#FFA500` | `io.tool_warning(...)` (e.g., model can't use tools warning). |
| `tool-error-color` | `#FF2222` | `io.tool_error(...)` (denied calls, malformed config, etc.). |
| `rule-color` | None | Divider/horizontal-rule lines. **New in this fork.** Falls back to user-input-color if unset. |
| `completion-menu-color` | None | Foreground of the slash-command completion popup. |
| `completion-menu-bg-color` | None | Background of the popup. |
| `completion-menu-current-color` | None | Foreground of the highlighted item. |
| `completion-menu-current-bg-color` | None | Background of the highlighted item. |
| `code-theme` | `default` | **Pygments** theme used inside code blocks (e.g. `monokai`, `solarized-dark`, `vim`). NOT a terminal color — it's the syntax-highlighting palette inside fenced ``` blocks. |

### `code-theme` is different

Worth calling out separately: `code-theme` is the Pygments style applied **inside** code blocks. It's not a terminal color setting. The list of valid values is whatever Pygments ships with — see <https://pygments.org/styles/>. Common picks: `monokai`, `default`, `solarized-dark`, `solarized-light`, `vim`, `github-dark`.

---

## Theme file format

Put your YAML theme anywhere readable; pass the path to `--color-theme`. Two accepted shapes:

### Flat mapping

```yaml
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
```

### Nested under `colors:`

```yaml
colors:
  assistant-output-color: "#7aa2f7"
  user-input-color: "#c0caf5"
  rule-color: "#7aa2f7"
  # ...
```

Both shapes work; pick whichever you like. Keys can use dashes (`assistant-output-color`) or underscores (`assistant_output_color`) — they're normalized internally.

Unknown keys are silently ignored, so you can keep theme-design notes in the same file:

```yaml
title: My theme
inspired-by: tokyo-night
license: MIT
colors:
  assistant-output-color: "#7aa2f7"
  # ...
```

---

## Override precedence

When you mix a preset with explicit settings, the rules are:

1. **Explicit per-color CLI flags / config-file values** win.
2. Then **theme file / preset values** for any color you didn't explicitly set.
3. Then **built-in defaults**.

So this:

```yaml
color-theme: dracula            # sets a full palette
assistant-output-color: "#ff8800"  # overrides just one
```

…produces a dracula-everything-except-assistant-text palette. The `apply_color_theme_overrides` logic in `aider/main.py` only fills in colors **the user didn't explicitly set** — it never overwrites your customization.

---

## Examples

### Tokyo-night with a hot-orange assistant

```yaml
color-theme: iterm-dark
assistant-output-color: "#ff8800"
rule-color: "#7aa2f7"
```

### Solarized-light with an even-more-Solarized rule color

```yaml
color-theme: solarized-light
rule-color: "#2aa198"
code-theme: solarized-light
```

### Custom file plus a single override

`~/.aider/themes/mine.yml`:

```yaml
colors:
  user-input-color: "#e6edf3"
  rule-color: "#7aa2f7"
  tool-output-color: "#9ece6a"
  tool-warning-color: "#e0af68"
  tool-error-color: "#f7768e"
  assistant-output-color: "#7aa2f7"
  code-theme: monokai
```

`.aider.conf.yml`:

```yaml
color-theme: /home/me/.aider/themes/mine.yml
assistant-output-color: "#ffaa00"   # warm assistant text on top of the file
```

---

## Implementation notes

The theme apparatus lives in `aider/main.py`:

- `OUTPUT_COLOR_DEFAULTS` — the source-of-truth set of overridable color keys and their built-in defaults.
- `COLOR_THEME_PRESETS` — the seven built-in palettes.
- `resolve_color_theme(name_or_path)` — returns the resolved color dict (preset by name, or YAML file by path).
- `apply_color_theme_overrides(args)` — walks the parsed args, applies theme values only where the user left the default in place.
- `print_color_theme_presets()` — invoked when you pass `--color-theme list` / `?` / `help`.

The actual color application happens later in `aider/io.py::InputOutput.__init__`, which validates each color string and falls back gracefully if you mistype one. Bad colors print a `tool_warning` and reset to None — they don't crash aider.
