# Multi-LLM Agent OS — Zellij Code Snippets

---

## 1. Create Zellij Session + Start Claude Code

```bash
#!/usr/bin/env bash
# create-agent-session.sh
SESSION="project-1"
TAB_NAME="claude-project1"

# Create session (detached) with named tab running Claude Code
zellij --session "$SESSION" options -- \
  --default-shell bash \
  action new-tab --name "$TAB_NAME" --command "claude" 2>/dev/null \
|| zellij --session "$SESSION" -- bash -c "claude"

# To attach from another terminal:
# zellij attach project-1
```

> If the session already exists, `zellij --session` attaches to it.
> The `--` separator passes the command as the initial pane command.

**One-liner shortcut:**
```bash
zellij --session project-1 -- claude
```

---

## 2. Live Zellij Terminal on a Web Page

### Option A — ttyd (recommended, easiest)
```bash
# Install
cargo install ttyd        # or: apt install ttyd / brew install ttyd

# Serve the zellij session on http://localhost:7681
ttyd -p 7681 -W zellij attach project-1

# Read-only view (no input):
ttyd -p 7681 -R zellij attach project-1
```

Embed in HTML with an iframe or use ttyd's built-in xterm.js UI at `http://localhost:7681`.

### Option B — Node.js + xterm.js + node-pty
```js
// server.js  (npm install ws node-pty xterm)
const pty  = require('node-pty');
const { WebSocketServer } = require('ws');

const wss = new WebSocketServer({ port: 7681 });
wss.on('connection', (ws) => {
  const shell = pty.spawn('zellij', ['attach', 'project-1'], {
    name: 'xterm-color', cols: 220, rows: 50,
  });
  shell.onData((data) => ws.send(data));
  ws.on('message', (msg) => shell.write(msg));
  ws.on('close', () => shell.kill());
});
console.log('Terminal WS on ws://localhost:7681');
```

```html
<!-- index.html — add xterm CSS/JS from CDN -->
<div id="terminal"></div>
<script>
  const term = new Terminal({ cursorBlink: true });
  term.open(document.getElementById('terminal'));
  const ws = new WebSocket('ws://localhost:7681');
  ws.onmessage = (e) => term.write(e.data);
  term.onData((d) => ws.send(d));
</script>
```

---

## 3–6. Capture Prompts & Responses → project1-chat.md

### Approach A — Shell Wrapper (non-interactive, `claude -p`)

Best for scripted/automated agents. `claude -p` sends a single prompt and returns.

```bash
#!/usr/bin/env bash
# agent-chat.sh
CHAT_FILE="project1-chat.md"
FIRST=true

# Initialize file on first run
if [ ! -f "$CHAT_FILE" ]; then
  echo "# project1-chat" > "$CHAT_FILE"
  echo "" >> "$CHAT_FILE"
fi

while true; do
  printf "You: "
  read -r prompt
  [[ -z "$prompt" ]] && continue

  # ── Step 3 / 5: Save user prompt ──────────────────────────
  if $FIRST; then
    echo "## Session started: $(date '+%Y-%m-%d %H:%M:%S')" >> "$CHAT_FILE"
    echo "" >> "$CHAT_FILE"
    FIRST=false
  fi

  echo "### User" >> "$CHAT_FILE"
  echo "$prompt" >> "$CHAT_FILE"
  echo "" >> "$CHAT_FILE"

  # ── Step 4 / 6: Capture LLM response ──────────────────────
  response=$(claude -p "$prompt" 2>&1)

  echo "### Claude" >> "$CHAT_FILE"
  echo "$response" >> "$CHAT_FILE"
  echo "" >> "$CHAT_FILE"
  echo "---" >> "$CHAT_FILE"
  echo "" >> "$CHAT_FILE"

  echo ""
  echo "$response"
  echo ""
done
```

---

### Approach B — Python PTY Wrapper (interactive `claude` session)

Use this when you need a live interactive Claude Code session (with tool use, multi-turn context, etc.) while still capturing I/O.

```python
#!/usr/bin/env python3
# pty_capture.py
import os, sys, pty, select, re, datetime

CHAT_FILE = "project1-chat.md"
PROMPT_MARKER = b"\x1b[0m"   # adjust to match claude's prompt ANSI reset

def strip_ansi(text: bytes) -> str:
    return re.sub(rb'\x1b\[[0-9;]*[mABCDEFGHJKSTfhinrsu]', b'', text).decode(errors='replace')

def append(role: str, text: str):
    with open(CHAT_FILE, "a") as f:
        f.write(f"### {role}\n{text.strip()}\n\n---\n\n")

def main():
    with open(CHAT_FILE, "a") as f:
        f.write(f"# project1-chat\n## Session: {datetime.datetime.now()}\n\n")

    master_fd, slave_fd = pty.openpty()
    pid = os.fork()

    if pid == 0:                          # child — run claude
        os.setsid()
        os.dup2(slave_fd, 0); os.dup2(slave_fd, 1); os.dup2(slave_fd, 2)
        os.close(master_fd); os.close(slave_fd)
        os.execvp("claude", ["claude"])
        sys.exit(1)

    os.close(slave_fd)
    user_buf, llm_buf = b"", b""
    capturing_llm = False

    while True:
        r, _, _ = select.select([master_fd, sys.stdin.fileno()], [], [], 0.1)
        for fd in r:
            if fd == master_fd:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    sys.exit(0)
                sys.stdout.buffer.write(data); sys.stdout.buffer.flush()
                llm_buf += data

            elif fd == sys.stdin.fileno():
                data = os.read(sys.stdin.fileno(), 1024)
                os.write(master_fd, data)
                if b"\n" in data:
                    line = strip_ansi(user_buf + data).strip()
                    if line:
                        append("User", line)
                    user_buf = b""
                    capturing_llm = True
                    llm_buf = b""
                else:
                    user_buf += data

        # Flush LLM buffer when output pauses (heuristic: 200ms idle)
        if capturing_llm and llm_buf and not r:
            clean = strip_ansi(llm_buf)
            if clean.strip():
                append("Claude", clean)
            llm_buf = b""
            capturing_llm = False

if __name__ == "__main__":
    main()
```

---

### Approach C — Zellij Plugin (`zellij-tile`) — capture via `pipe`

Wire a running Claude pane's output back into a plugin using `zellij pipe`.

```rust
// src/main.rs  (Cargo.toml: zellij-tile = "0.44.3")
use zellij_tile::prelude::*;
use std::collections::BTreeMap;

#[derive(Default)]
struct ChatLogger {
    first_prompt: bool,
}

register_plugin!(ChatLogger);

impl ZellijPlugin for ChatLogger {
    fn load(&mut self, _config: BTreeMap<String, String>) {
        self.first_prompt = true;
        subscribe(&[EventType::Key, EventType::PaneUpdate]);
        request_permission(&[
            PermissionType::RunCommands,
            PermissionType::WriteToStdin,
            PermissionType::ReadApplicationState,
        ]);
    }

    /// Receives piped data — call from shell:
    ///   echo "$PROMPT" | zellij pipe --plugin file:chat-logger.wasm -- ""
    ///   echo "$RESPONSE" | zellij pipe --name llm_response --plugin file:chat-logger.wasm -- ""
    fn pipe(&mut self, msg: PipeMessage) -> bool {
        let payload = msg.payload.unwrap_or_default();
        let role = if msg.name == "llm_response" { "Claude" } else { "User" };
        let entry = format!("### {role}\n{payload}\n\n---\n\n");

        run_command(
            &["bash", "-c", &format!("echo '{entry}' >> project1-chat.md")],
            BTreeMap::new(),
        );
        false
    }

    fn render(&mut self, _rows: usize, _cols: usize) {}
}
```

**Shell side — send events to the plugin:**
```bash
# User sends a prompt:
echo "$USER_PROMPT" | zellij pipe --name user_prompt \
  --plugin file:target/wasm32-wasi/debug/chat-logger.wasm -- ""

# After getting response, send it:
echo "$LLM_RESPONSE" | zellij pipe --name llm_response \
  --plugin file:target/wasm32-wasi/debug/chat-logger.wasm -- ""
```

---

## 7. Send Commands to Panes — zellij-send-keys

### Setup (one time — grants permissions)
```bash
zellij plugin -- file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm
```

### List panes + their IDs
```bash
# Current session
ZELLIJ_SESSION_NAME=project-1 zellij action pipe \
  --plugin file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm \
  --name list_panes

# Returns JSON: [{"pane_id": 0, "title": "claude"}, {"pane_id": 1, ...}]
```

### Send to a pane in the SAME session
```bash
ZELLIJ_SESSION_NAME=project-1 zellij action pipe \
  --plugin file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm \
  --name send_keys \
  -- '{"pane_id": 0, "text": "build me a REST API", "send_enter": true}'

# Without pressing Enter (pre-fill only):
  -- '{"pane_id": 0, "text": "partial input"}'
```

### Send to a pane in a DIFFERENT session
```bash
# Just change ZELLIJ_SESSION_NAME — same command otherwise
ZELLIJ_SESSION_NAME=project-2 zellij action pipe \
  --plugin file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm \
  --name send_keys \
  -- '{"pane_id": 0, "text": "your prompt here", "send_enter": true}'
```

### Helper function (add to ~/.zshrc)
```bash
send_to_pane() {
  local session="$1"
  local pane_id="$2"
  local text="$3"
  local send_enter="${4:-true}"

  ZELLIJ_SESSION_NAME="$session" zellij action pipe \
    --plugin file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm \
    --name send_keys \
    -- "{\"pane_id\": $pane_id, \"text\": \"$text\", \"send_enter\": $send_enter}"
}

# Usage:
# send_to_pane project-1 0 "build me a REST API"
# send_to_pane project-2 1 "partial text" false
```

### Multi-agent broadcast (same prompt to all sessions)
```bash
broadcast_to_agents() {
  local prompt="$1"
  local sessions=("project-1" "project-2" "project-3")

  for session in "${sessions[@]}"; do
    ZELLIJ_SESSION_NAME="$session" zellij action pipe \
      --plugin file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm \
      --name send_keys \
      -- "{\"pane_id\": 0, \"text\": \"$prompt\", \"send_enter\": true}"
  done
}

# Usage:
# broadcast_to_agents "summarize your current task status"
```

---

## Putting It Together — Full Flow

```bash
#!/usr/bin/env bash
# run-agent.sh — combines session creation + I/O capture

SESSION="project-1"
CHAT_FILE="project1-chat.md"

# 1. Create session (no-op if exists)
zellij --session "$SESSION" options 2>/dev/null || true

# 2. (Optional) Serve web terminal
ttyd -p 7681 -W zellij attach "$SESSION" &
echo "Web terminal: http://localhost:7681"

# 3-6. Run the chat loop
bash agent-chat.sh          # or: python3 pty_capture.py
```

---

## 8. Resizable Web Workspace — xterm.js + Zellij WebSocket + split.js

Connects xterm.js directly to Zellij's built-in WebSocket endpoints and puts each
terminal inside a draggable split pane — same pattern as amux/zellij-web UIs.

```html
<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.css">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #1e1e2e; height: 100vh; display: flex; flex-direction: column; }
    .workspace { display: flex; flex: 1; overflow: hidden; }
    .pane { overflow: hidden; position: relative; min-width: 100px; }
    .pane-header {
      background: #181825; color: #cdd6f4;
      font: 12px 'JetBrains Mono', monospace;
      padding: 4px 12px; border-bottom: 1px solid #313244;
      display: flex; justify-content: space-between;
    }
    .terminal-container { height: calc(100% - 25px); padding: 4px; }
    .gutter {
      background: #313244; cursor: col-resize;
      width: 4px; flex-shrink: 0;
    }
    .gutter:hover { background: #89b4fa; }
  </style>
</head>
<body>
  <div class="workspace">
    <div class="pane" id="pane-0">
      <div class="pane-header"><span>project-1</span><span>claude</span></div>
      <div class="terminal-container" id="term-0"></div>
    </div>
    <div class="gutter"></div>
    <div class="pane" id="pane-1">
      <div class="pane-header"><span>project-2</span><span>claude</span></div>
      <div class="terminal-container" id="term-1"></div>
    </div>
  </div>

  <script src="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/xterm.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/xterm/5.3.0/addon-fit.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/split.js/1.6.5/split.min.js"></script>
  <script>
    const ZELLIJ = 'wss://terminal.ackgent.com:8082';

    function createZellijTerminal(containerId, session) {
      const container = document.getElementById(containerId);
      const term = new Terminal({
        cursorBlink: true,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 14,
        theme: { background: '#1e1e2e', foreground: '#cdd6f4' }
      });
      const fitAddon = new FitAddon.FitAddon();
      term.loadAddon(fitAddon);
      term.open(container);
      fitAddon.fit();

      // Connect to Zellij WebSocket endpoints
      const clientId = crypto.randomUUID();
      const wsTerminal = new WebSocket(
        `${ZELLIJ}/ws/terminal/${session}?web_client_id=${clientId}`
      );
      const wsControl = new WebSocket(`${ZELLIJ}/ws/control`);

      wsTerminal.onmessage = (e) => term.write(e.data);
      term.onData((data) => wsTerminal.send(data));

      // Notify Zellij of new dimensions whenever container resizes
      const sendResize = () => {
        fitAddon.fit();
        wsControl.send(JSON.stringify({
          web_client_id: clientId,
          payload: { type: 'TerminalResize', rows: term.rows, cols: term.cols }
        }));
      };

      new ResizeObserver(sendResize).observe(container);
      wsControl.onopen = sendResize;

      return term;
    }

    // Draggable split — add more panes/gutters in HTML to extend
    Split(['#pane-0', '#pane-1'], {
      sizes: [50, 50], minSize: 200, gutterSize: 4,
      onDrag: () => window.dispatchEvent(new Event('resize'))
    });

    // Connect each pane to a named Zellij session
    createZellijTerminal('term-0', 'project-1');
    createZellijTerminal('term-1', 'project-2');
  </script>
</body>
</html>
```

**Key points:**
- Auth is handled by the `session_token` cookie set after logging in via `/command/login` — no token needed in the JS
- `ResizeObserver` fires on every drag, sending updated `rows`/`cols` to Zellij's control socket so the terminal reflows correctly
- Add a notes pane by inserting a plain `<div>` (no xterm) in the same split alongside terminal panes
- For horizontal splits, change `direction: 'vertical'` in Split() options and `flex-direction: column` in `.workspace`

---

## project1-chat.md Output Format

```markdown
# project1-chat
## Session: 2026-06-15 10:00:00

### User
Build me a REST API for user auth

### Claude
Here's a JWT-based auth API...

---

### User
Add refresh token support

### Claude
To add refresh tokens...

---
```
