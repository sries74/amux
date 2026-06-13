# amux tmux Command Reference

Every tmux invocation in `amux-server.py` (and supporting files), organized by component.

---

## Table of Contents

1. [Session Lifecycle](#1-session-lifecycle)
2. [Session Configuration](#2-session-configuration)
3. [Input / Send Keys](#3-input--send-keys)
4. [Output Capture](#4-output-capture)
5. [Pane Management](#5-pane-management)
6. [Log Piping](#6-log-piping)
7. [Status Detection](#7-status-detection)
8. [Session Adoption / Migration](#8-session-adoption--migration)
9. [Environment Variables](#9-environment-variables)
10. [Window Management](#10-window-management)
11. [Data Cleanup](#11-data-cleanup)
12. [tmux.conf (server provisioning)](#12-tmuxconf-server-provisioning)

---

## 1. Session Lifecycle

### `tmux new-session` — Create a new agent session

```python
subprocess.run([
    "tmux", "new-session",
    "-d",                    # detached (background)
    "-s", tmux_sess,         # session name (amux-<name>)
    "-n", name,              # window name
    "-c", work_dir,          # working directory
    "-e", "TMUX_SESSION_NAME=" + name,   # env var: logical session name
    "-e", "AMUX_SESSION=" + name,        # env var: amux session name
    "-e", "AMUX_URL=https://localhost:8822",  # env var: dashboard URL
    *_env_args,              # additional env vars (ANTHROPIC_API_KEY, etc.)
    _USER_SHELL,             # shell to launch (bash/zsh)
])
```

**Component:** `create_session()` / session start flow  
**What it does:** Creates a new detached tmux session running the user's shell in the project directory. Environment variables are injected so Claude Code can discover the amux dashboard and API key. The session is the container for a Claude Code agent.

---

### `tmux has-session` — Check if a session exists

```python
subprocess.run(["tmux", "has-session", "-t", tmux_name(session)])
```

**Component:** `is_running()`, `session_exists()`  
**What it does:** Returns exit code 0 if the named tmux session exists, non-zero otherwise. Used to check whether a session is live before operating on it (start, stop, capture, rename, etc.).

---

### `tmux kill-session` — Destroy a session

```python
subprocess.run(["tmux", "kill-session", "-t", tmux_name(name)])
```

**Component:** `_kill_tmux_session()`, `stop_session()`, `_enforce_archived_stopped()`  
**What it does:** Forcefully kills a tmux session and all its panes. Used when a user deletes a session from the dashboard, during auto-archive of idle sessions, and as a last resort when graceful stop fails (after `pkill -9` on the Claude PID doesn't work).

---

### `tmux list-sessions` — List all sessions

```python
# Simple list of session names:
subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"])

# With pipe-pane cleanup:
subprocess.run(["tmux", "list-sessions"])
```

**Component:** `list_tmux_sessions()`, `_server_env_watcher()` (pushing API keys)  
**What it does:** Lists all tmux sessions. Used to find unregistered sessions for the "Connect to tmux" UI, and to iterate over all sessions when pushing updated environment variables (e.g., a new `ANTHROPIC_API_KEY`).

---

## 2. Session Configuration

### `tmux set-option` — Set session options

```python
subprocess.run(["tmux", "set-option", "-t", tmux_sess, "remain-on-exit", "on"])
subprocess.run(["tmux", "set-option", "-t", tmux_sess, "allow-rename", "off"])
```

**Component:** `create_session()` (immediately after `new-session`)  
**What it does:**
- `remain-on-exit on` — Keeps the pane alive (showing exit output) even if the shell or Claude Code crashes. This prevents the window from disappearing and lets the user see the error.
- `allow-rename off` — Prevents tmux from auto-renaming the session if something inside the pane tries to change it.

---

### `tmux set-window-option` — Set window options

```python
subprocess.run(["tmux", "set-window-option", "-t", tmux_sess, "automatic-rename", "off"])
```

**Component:** `create_session()`  
**What it does:** Disables tmux's automatic window renaming based on the active process. Without this, window names would change to reflect whatever Claude is doing (e.g., showing the current file being edited). Keeps the window name stable.

---

## 3. Input / Send Keys

### `tmux send-keys` — Send keystrokes to a session

**Component:** `send_keys()`, `send_command()`, `stop_session()`, session creation, self-healing watchdog.

All `send-key` invocations:

| Flags | What it does | Component |
|-------|-------------|-----------|
| `C-c` | Send Ctrl+C (interrupt current Claude operation) | `stop_session()`, self-healing (unstuck) |
| `C-u` | Send Ctrl+U (clear input line) | Pre-command line clearing |
| `Escape` | Send Escape key | Stop/cancel operations |
| `Enter` | Send Enter key (submit) | `send_keys()` after literal text |
| `-l "stty sane"` | Reset terminal to sane state | Session start / crash recovery |
| `-l "HISTFILE=/dev/null"` | Disable shell history file | Session start (prevent bash history spam in Claude sessions) |
| "-l \"cd <dir>\"" | Change working directory | Session start (`-c` sets initial dir, this re-confirms it) |
| `-l <shell_rc>` | Source shell rc file (source ~/.bashrc etc.) | Session start — ensure PATH and env are loaded |
| `-l <cmd>` | Send literal text then Enter | `send_command()` — main way to send prompts to Claude |
| `-l <cmd_fresh>` | Send fresh command text (with history clear) | Self-healing watchdog restart |
| `-l "/exit"` | Send `/exit` to Claude | Graceful Claude shutdown |
| `-l "/rename <name>"` | Send `/rename` to Claude | Self-healing rename recovery |
| `-l <prompt>` | Send literal prompt text | Session clone / fork replay |
| `keys` (variable) | Send arbitrary keys (from API) | `send_keys()` endpoint — allows sending special keys |

**What it does in general:** Injects keystrokes into the target tmux pane as if the user typed them. The `-l` flag sends *literal* text (not interpreted as tmux key names). This is amux's primary mechanism for controlling Claude Code — every prompt, interrupt, and reset goes through `send-keys`.

---

## 4. Output Capture

### `tmux capture-pane` — Capture terminal output

```python
# Primary capture (with ANSI escape codes, scrollback):
subprocess.run([
    "tmux", "capture-pane",
    "-t", tmux_target(session),  # target pane
    "-p",                        # print to stdout
    "-e",                        # include ANSI escape codes (colors)
    "-S", f"-{lines}",          # start N lines from bottom (scrollback)
])

# Plain capture (bottom of pane):
subprocess.run([
    "tmux", "capture-pane",
    "-t", tmux_target(name), "-p", "-S", "-50"
])

# Full scrollback capture (for fork/clone):
subprocess.run([
    "tmux", "capture-pane",
    "-t", tmux_target(name), "-p", "-S", "-3000"
])

# Capture without ANSI codes:
subprocess.run([
    "tmux", "capture-pane",
    "-t", tmux_target(name), "-p"
])
```

**Component:** `tmux_capture()`, `_peek()`, fork/clone, status detection, self-healing  
**What it does:** Reads the visible terminal content (scrollback buffer) of a tmux pane. This is how amux:
- Shows live output in the web dashboard (Peek mode)
- Detects Claude's status (working/waiting/idle/error) by parsing ANSI-stripped output
- Captures conversation history when forking or cloning a session
- Detects rate-limit prompts, thinking-block corruption, and stuck states
- Checks for shell prompt after graceful stop (`_at_shell_prompt()`)

---

## 5. Pane Management

### `tmux display-message` — Query pane/session properties

```python
# Get current working directory of a pane:
subprocess.run([
    "tmux", "display-message",
    "-t", tmux_session,
    "-p",                    # print to stdout
    "#{pane_current_path}"   # format: current directory path
])

# Get pane last activity time (for idle detection):
subprocess.run([
    "tmux", "display-message",
    "-t", tmux_target(name),
    "-p",
    "#{pane_activity}"        # format: Unix timestamp of last activity
])
```

**Component:** `openConnect()` / session adoption, `_auto_archive_idle()`  
**What it does:**
- `#{pane_current_path}` — Used when connecting to an existing tmux session: reads the pane's current directory so amux knows which project the session is working in.
- `#{pane_activity}` — Returns the Unix timestamp of the last time the pane had output. Used by the auto-archive system to detect sessions that have been idle for too long (default threshold configurable via `_IDLE_ARCHIVE_HOURS`).

---

### `tmux respawn-pane` — Restart the pane process

```python
subprocess.run([
    "tmux", "respawn-pane",
    "-k",              # kill existing process first
    "-t", tmux_target(name),
    _USER_SHELL,       # respawn with the user's shell (bash/zsh)
])
```

**Component:** Crash recovery / hard restart  
**What it does:** Kills whatever process is running in the pane (Claude Code or shell) and starts a fresh shell. This is amux's hard restart mechanism — used when Claude crashes or the pane is in an unrecoverable state. The session stays alive; only the pane content is reset.

---

### `tmux list-panes` — List panes and their PIDs

```python
# Per-session pane PID:
subprocess.run([
    "tmux", "list-panes",
    "-t", tmux_target(name),
    "-F", "#{pane_pid}"    # format: PID of the process in the pane
])

# All sessions pane mapping:
subprocess.run([
    "tmux", "list-panes",
    "-a",                                    # all sessions
    "-F", "#{session_name} #{pane_pid}"      # format: session→PID mapping
])

# Extended pane info (for sidebar):
subprocess.run([
    "tmux", "list-panes",
    "-a",
    "-F", "#{session_name}\t#{window_activity}\t#{session_created}\t#{pane_title}"
])
```

**Component:** `get_claude_pid()`, `build_tmux_map()`, sidebar session list  
**What it does:**
- `#{pane_pid}` — Returns the PID of the foreground process in the pane. Used to find the Claude Code process PID so it can be `pkill -9`'d during hard stops.
- The all-sessions variant builds a mapping from session names to PIDs, used to determine which sessions have running Claude processes.
- The extended format (`window_activity`, `session_created`, `pane_title`) is used by the web dashboard sidebar to show session metadata.

---

## 6. Log Piping

### `tmux pipe-pane` — Stream pane output to a file

```python
# Start piping:
subprocess.run([
    "tmux", "pipe-pane",
    "-t", tmux_name(name),
    "-o",                                    # overwrite (not append)
    _log_pipe_command(lp),                   # output redirect command
])

# Stop piping (detach):
subprocess.run(["tmux", "pipe-pane", "-t", tmux_name(name)])
subprocess.run(["tmux", "pipe-pane", "-t", tmux_sess])
```

**Component:** `start_log_pipe()`, `stop_log_pipe()`  
**What it does:** Streams all terminal output from the pane to a log file in real-time. When a session starts, amux begins piping output to `~/.amux/logs/<name>.log`. This provides persistent output history that survives restarts. The pipe is detached before sending commands to the pane (to avoid the pipe command itself appearing in output) and re-attached afterward.

---

## 7. Status Detection

### `tmux capture-pane` + ANSI parsing (read-only see §4)

Status detection itself is pure Python parsing of `tmux capture-pane` output, but two specific patterns are worth noting:

- **Rate-limit detection:** Scans captured output for Claude's rate-limit menu (❯ 1. Stop and wait for limit to reset / 2. Add funds / 3. Upgrade). When detected, the watchdog uses `send-keys` to auto-select option 1.
- **Shell prompt detection:** After a stop command, captures pane output looking for the shell prompt (`$`, `#`, `>`) to confirm Claude exited cleanly.

---

## 8. Session Adoption / Migration

### `tmux has-session` + `tmux rename-session` — Adopt existing sessions

```python
# Check for legacy names (cmux-*/cc-*) and migrate:
for old in [f"cmux-{session}", f"cc-{session}"]:
    r = subprocess.run(["tmux", "has-session", "-t", old], ...)
    if r.returncode == 0:
        subprocess.run(["tmux", "rename-session", "-t", old, new])

# After connecting an external session:
if tmux_session != expected_tmux:
    subprocess.run([
        "tmux", "rename-session",
        "-t", tmux_session,
        expected_tmux,    # amux-<name> format
    ])
```

**Component:** `tmux_name()` (migration), `/api/sessions/connect` (adoption)  
**What it does:** When registering a new session, checks if the session already exists under legacy naming conventions (`cmux-*` or `cc-*`) and renames them to the `amux-*` convention. When a user connects to an external tmux session via the UI, renames it to match the amux naming scheme.

---

## 9. Environment Variables

### `tmux set-environment` — Set env vars in running sessions

```python
subprocess.run([
    "tmux", "set-environment",
    "-t", sn,                          # session name
    "ANTHROPIC_API_KEY", _new_key,     # key, value
])
```

**Component:** `_server_env_watcher()` (monitors `~/.amux/server.env`), `_update_settings()`  
**What it does:** Pushes updated environment variables into all running tmux sessions without restarting them. Called when the user updates `ANTHROPIC_API_KEY` in settings or when `server.env` changes on disk. Iterates over all sessions from `tmux list-sessions` and sets the variable in each one.

---

## 10. Window Management

### `tmux rename-window` — Rename a session's window

```python
subprocess.run([
    "tmux", "rename-window",
    "-t", tmux_sess,
    name,       # new window name (session name without amux- prefix)
])
```

**Component:** `create_session()`  
**What it does:** After creating the session, renames the window (not the session) to the human-readable name. The session is named `amux-<name>` but the window title shows just `<name>`, making it easier to browse sessions in `tmux choose-tree`.

---

## 11. Data Cleanup

### `tmux clear-history` — Clear scrollback history

```python
subprocess.run([
    "tmux", "clear-history",
    "-t", tmux_target(name),
])
```

**Component:** Fork/clone cleanup  
**What it does:** Clears the pane's scrollback buffer before replaying conversation history during a session fork or clone. This ensures the cloned session starts with a clean terminal and only shows the replayed conversation, not the original session's raw output.

---

### `tmux load-buffer` / `tmux paste-buffer` — Paste large text safely

```python
# Load text into a named buffer:
subprocess.run([
    "tmux", "load-buffer",
    "-b", buf_name,    # named buffer (unique per send)
    tmp,               # temp file containing the text
])

# Paste the buffer literally:
subprocess.run([
    "tmux", "paste-buffer",
    "-p",              # paste literally (not interpreted as keypresses)
    "-b", buf_name,
    "-t", t,           # target pane
])

# Clean up named buffer after send:
subprocess.run([
    "tmux", "delete-buffer",
    "-b", buf_name,
])
```

**Component:** `send_keys()` — long text safe send mechanism  
**What it does:** For long prompts, instead of using `send-keys` (which can split text at newlines since tmux interprets `\n` as Enter), amux writes the text to a temp file, loads it into a tmux named buffer, pastes it literally into the pane, then deletes the buffer. This prevents text from being split mid-sentence.

---

## 12. `.tmux.conf` (Server Provisioning)

Configured in `cloud/setup.sh` for GCP cloud deployments:

```tmux
set -g mouse on                    # Enable mouse scrolling/clicking
set -g history-limit 50000         # 50k lines of scrollback (default: 2000)
set -g default-terminal "screen-256color"  # 256-color support
set -g status-style "bg=colour235,fg=colour248"  # Status bar colors (dark gray)
set -g status-left " #[fg=colour39,bold] amux-cloud #[default]"  # "amux-cloud" label
set -g status-right " #[fg=colour245]%H:%M "  # Clock on the right
set -g base-index 1                # Sessions start at index 1 (not 0)
setw -g pane-base-index 1          # Panes start at index 1 (not 0)
```

**Component:** Cloud provisioning (`cloud/setup.sh`)  
**What it does:** Sets up tmux for the production cloud machine. Large history buffer is critical because amux reads scrollback for status detection and fork/clone operations. The `screen-256color` terminal type ensures Claude Code's colored output renders correctly.
