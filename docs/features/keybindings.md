# Keybindings

The fork inherits aider's keybindings and adds **Shift+Enter as an alias for Alt+Enter** so muscle memory from Slack, Discord, ChatGPT, Claude Desktop, etc. doesn't bite when typing prompts.

## Default bindings

| Key | Normal mode | Multiline mode (`/multiline-mode`) |
|---|---|---|
| `Enter` | Submit | Insert newline |
| `Alt+Enter` | Insert newline | Submit |
| `Shift+Enter` | Insert newline (alias for Alt+Enter) | Submit (alias for Alt+Enter) |
| `Ctrl+P` | Open command palette | Open command palette |
| `Ctrl+X Ctrl+E` | Edit current input in $EDITOR | Same |
| `Ctrl+Up` / `Ctrl+Down` | History prev/next | History prev/next |
| `Ctrl+C` | Cancel current input / interrupt streaming | Same |
| `Ctrl+D` | Exit at empty prompt | Same |

## Why Shift+Enter needs terminal config

Most terminals can't distinguish `Shift+Enter` from plain `Enter` by default — both send `\r` (carriage return). To make Shift+Enter work as a separate key, you need to configure your terminal to send a different sequence. Aider listens for `\n` (Ctrl-J / Line Feed) on this binding, so any terminal config that maps `Shift+Enter` → `\n` will work.

### iTerm2 (macOS)

Preferences → Profiles → Keys → Key Mappings → `+` (add)

| Field | Value |
|---|---|
| Keyboard Shortcut | press `Shift+Enter` |
| Action | "Send Text with vim Special Chars" |
| Text | `\n` |

### Alacritty

Add to `~/.config/alacritty/alacritty.toml`:

```toml
[[keyboard.bindings]]
key = "Return"
mods = "Shift"
chars = "
"
```

### Kitty

Add to `~/.config/kitty/kitty.conf`:

```
map shift+enter send_text all \x0a
```

### WezTerm

Add to `~/.wezterm.lua`:

```lua
config.keys = {
  { key = 'Enter', mods = 'SHIFT', action = wezterm.action.SendString '\n' },
}
```

### Ghostty

In `~/.config/ghostty/config`:

```
keybind = shift+enter=text:\n
```

### Windows Terminal

Add to your `settings.json` actions:

```json
{ "command": { "action": "sendInput", "input": "\n" }, "keys": "shift+enter" }
```

### Tmux note

If you run aider inside tmux and Shift+Enter still doesn't work, your tmux session may be eating or remapping the sequence. The terminal config above sends `\n` directly which most tmux configs pass through cleanly. If issues persist, ensure tmux's `xterm-keys` is enabled:

```
set -g xterm-keys on
```

## What if I don't want to configure my terminal?

Alt+Enter still works exactly as it always did. The Shift+Enter binding is purely additive — no breakage if the terminal isn't configured.

## Implementation notes

The binding is in `aider/io.py` as `@kb.add("c-j", ...)` paralleling the existing `@kb.add("escape", "enter", ...)` for Alt+Enter. Both handle the same logic: in normal mode insert a newline, in multiline mode submit. Catching `Ctrl-J` was chosen over fancy CSI escape parsing because every modern terminal can be configured to send `\n` on Shift+Enter, and the binding is a single line of prompt_toolkit configuration.
