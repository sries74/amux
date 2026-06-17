# Multi-LLM Agent OS — Advanced Snippets

> All snippets assume the helper function from the main snippets file is in `~/.zshrc`:
> `send_to_pane <session> <pane_id> "<text>" [true|false]`

---

## Base helper (required by all snippets below)

```bash
# ~/.zshrc
PLUGIN="file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm"

send_to_pane() {
  local session="$1" pane_id="$2" text="$3" send_enter="${4:-true}"
  ZELLIJ_SESSION_NAME="$session" zellij action pipe \
    --plugin "$PLUGIN" --name send_keys \
    -- "{\"pane_id\": $pane_id, \"text\": \"$text\", \"send_enter\": $send_enter}"
}
```

---

## 1. Orchestration — Chain agent output into next agent's input

```bash
#!/usr/bin/env bash
# chain-agents.sh
# Agent-1 answers a prompt → its response becomes agent-2's context

SESSION_1="project-1"
SESSION_2="project-2"
PANE=0
OUTFILE="/tmp/agent1-response.txt"

# Send prompt to agent-1 via claude -p (captures output cleanly)
echo "Summarize the auth module in 3 bullet points" \
  | claude -p > "$OUTFILE"

# Read the response and inject into agent-2 as context
RESPONSE=$(cat "$OUTFILE")
send_to_pane "$SESSION_2" $PANE "Context from agent-1: $RESPONSE. Now implement the auth tests."
```

---

## 2. Orchestration — Round-robin task distribution

```bash
#!/usr/bin/env bash
# round-robin.sh
# Distributes a task list across agent panes evenly

SESSIONS=("project-1" "project-2" "project-3")
PANE=0
TASKS=(
  "implement user login endpoint"
  "implement user registration endpoint"
  "implement password reset endpoint"
  "implement JWT refresh endpoint"
  "write tests for all auth endpoints"
)

for i in "${!TASKS[@]}"; do
  session="${SESSIONS[$((i % ${#SESSIONS[@]}))]}"
  echo "→ Sending task $((i+1)) to $session"
  send_to_pane "$session" $PANE "${TASKS[$i]}"
  sleep 0.5  # small delay to avoid overwhelming
done
```

---

## 3. Orchestration — Manager/worker pattern

```bash
#!/usr/bin/env bash
# manager-worker.sh
# Manager agent in pane 0 breaks down a task,
# output is parsed and distributed to worker agents

MANAGER_SESSION="manager"
WORKER_SESSIONS=("worker-1" "worker-2" "worker-3")
PANE=0

# Ask manager to produce a task list (one task per line)
TASKS=$(echo "Break down 'build a REST API for a blog' into 3 isolated subtasks, one per line, no numbering" \
  | claude -p)

echo "Manager produced:"
echo "$TASKS"
echo ""

# Send each line to a worker
i=0
while IFS= read -r task; do
  [[ -z "$task" ]] && continue
  session="${WORKER_SESSIONS[$((i % ${#WORKER_SESSIONS[@]}))]}"
  echo "→ $session: $task"
  send_to_pane "$session" $PANE "$task"
  ((i++))
done <<< "$TASKS"
```

---

## 4. Control signals — Send Ctrl+C / Ctrl+D / quit

```bash
#!/usr/bin/env bash
# control-signals.sh

PLUGIN="file:/home/scott/.config/zellij/plugins/zellij-send-keys.wasm"

# Ctrl+C (cancel running command) — Unicode 
send_ctrl_c() {
  local session="$1" pane_id="$2"
  ZELLIJ_SESSION_NAME="$session" zellij action pipe \
    --plugin "$PLUGIN" --name send_keys \
    -- "{\"pane_id\": $pane_id, \"text\": \"\", \"send_enter\": false}"
}

# Ctrl+D (EOF / exit shell)
send_ctrl_d() {
  local session="$1" pane_id="$2"
  ZELLIJ_SESSION_NAME="$session" zellij action pipe \
    --plugin "$PLUGIN" --name send_keys \
    -- "{\"pane_id\": $pane_id, \"text\": \"\", \"send_enter\": false}"
}

# Clean exit
send_exit() {
  local session="$1" pane_id="$2"
  send_to_pane "$session" $pane_id "exit"
}

# Cancel all agents
cancel_all() {
  for session in "project-1" "project-2" "project-3"; do
    send_ctrl_c "$session" 0
    echo "Cancelled $session"
  done
}
```

---

## 5. Health checks — Verify agents are alive

```bash
#!/usr/bin/env bash
# health-check.sh
# Sends a known prompt to each agent and checks for a response

SESSIONS=("project-1" "project-2" "project-3")
PANE=0
TIMEOUT=30

check_agent() {
  local session="$1"
  local probe="Reply with only the word ALIVE"
  local outfile="/tmp/health-$session.txt"

  response=$(echo "$probe" | timeout $TIMEOUT claude -p 2>/dev/null)

  if echo "$response" | grep -qi "alive"; then
    echo "✓ $session — healthy"
  else
    echo "✗ $session — not responding (restarting...)"
    send_to_pane "$session" $PANE "exit"
    sleep 1
    ZELLIJ_SESSION_NAME="$session" zellij action new-pane -- claude
  fi
}

for session in "${SESSIONS[@]}"; do
  check_agent "$session" &
done
wait
echo "Health check complete."
```

---

## 6. Context injection — Auto-send system prompt on session start

```bash
#!/usr/bin/env bash
# start-agent.sh
# Creates a session, starts claude, injects system context before user types

SESSION="${1:-project-1}"
PANE=0
SYSTEM_PROMPT="You are an expert Rust developer working on a Zellij plugin. 
The project uses zellij-tile 0.44.3. 
Always use idiomatic Rust. Prefer small focused functions."

# Start session with claude
zellij --session "$SESSION" -- claude &
sleep 2  # wait for claude to initialize

# Inject context
send_to_pane "$SESSION" $PANE "$SYSTEM_PROMPT"
echo "Agent $SESSION ready with context injected."
```

---

## 7. Context injection — Send file contents into a pane

```bash
#!/usr/bin/env bash
# inject-file.sh
SESSION="${1:-project-1}"
PANE=0
FILE="${2}"

if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Usage: inject-file.sh <session> <file>"
  exit 1
fi

CONTENT=$(cat "$FILE")
PROMPT="Here is the file $FILE:\n\`\`\`\n$CONTENT\n\`\`\`\nReview it and suggest improvements."

send_to_pane "$SESSION" $PANE "$PROMPT"
```

---

## 8. Cross-model critique — Claude → second model review

```bash
#!/usr/bin/env bash
# cross-model-review.sh
# Claude writes code → sends it to a second agent for critique

PRIMARY_SESSION="claude-primary"
CRITIC_SESSION="claude-critic"
PANE=0

TASK="Write a Python function that validates an email address using regex"

# Get primary output
echo "Sending task to primary agent..."
PRIMARY_RESPONSE=$(echo "$TASK" | claude -p)

echo "Primary response received. Sending to critic..."

# Send to critic with critique framing
CRITIQUE_PROMPT="Review this code for bugs, edge cases, and improvements:\n\n$PRIMARY_RESPONSE"
send_to_pane "$CRITIC_SESSION" $PANE "$CRITIQUE_PROMPT"

echo "Done. Check $CRITIC_SESSION pane for critique."
```

---

## 9. Git hooks — Auto-prompt agent on commit

```bash
#!/usr/bin/env bash
# .git/hooks/post-commit
# chmod +x .git/hooks/post-commit

source ~/.zshrc  # load send_to_pane

SESSION="project-1"
PANE=0

# Get the diff of the last commit
DIFF=$(git diff HEAD~1 HEAD --stat)
FULL_DIFF=$(git diff HEAD~1 HEAD)

PROMPT="I just committed these changes:\n\n$DIFF\n\nFull diff:\n$FULL_DIFF\n\nAny issues or improvements to note?"

send_to_pane "$SESSION" $PANE "$PROMPT"
echo "→ Sent commit diff to agent in $SESSION"
```

```bash
# .git/hooks/pre-commit — send diff for review BEFORE committing
#!/usr/bin/env bash
source ~/.zshrc

SESSION="project-1"
PANE=0

STAGED=$(git diff --cached)
[[ -z "$STAGED" ]] && exit 0

PROMPT="Review this staged diff before I commit it:\n\n$STAGED\n\nAny bugs or issues?"
send_to_pane "$SESSION" $PANE "$PROMPT"

echo "→ Sent staged diff to agent. Check $SESSION before confirming commit."
# Don't block the commit — remove 'exit 1' if you want to block
```

---

## 10. File watcher — Auto-send changed file to agent on save

```bash
#!/usr/bin/env bash
# watch-and-send.sh
# Watches a file/dir and sends contents to agent on every save
# Requires: inotifywait (apt install inotify-tools)

SESSION="${1:-project-1}"
PANE=0
WATCH_PATH="${2:-.}"  # default: current dir

echo "Watching $WATCH_PATH — changes will be sent to $SESSION pane $PANE"

inotifywait -m -r -e close_write --format '%w%f' "$WATCH_PATH" \
  | grep -E '\.(rs|py|js|ts|go|sh)$' \
  | while read -r filepath; do
      echo "→ Changed: $filepath"
      CONTENT=$(cat "$filepath")
      PROMPT="I just saved $filepath. Review the changes:\n\`\`\`\n$CONTENT\n\`\`\`"
      send_to_pane "$SESSION" $PANE "$PROMPT"
    done
```

---

## 11. Log tailer — Send errors to agent for live debugging

```bash
#!/usr/bin/env bash
# tail-errors.sh
# Tails a log file and sends ERROR lines to an agent automatically

SESSION="${1:-project-1}"
PANE=0
LOG_FILE="${2:-/var/log/syslog}"
BATCH_SIZE=5       # send after this many errors accumulate
BATCH_TIMEOUT=10   # or after this many seconds

echo "Tailing $LOG_FILE → sending errors to $SESSION"

error_buf=()
last_send=$(date +%s)

tail -F "$LOG_FILE" | grep --line-buffered -i "error\|exception\|fatal\|panic" \
  | while IFS= read -r line; do
      error_buf+=("$line")
      now=$(date +%s)
      elapsed=$(( now - last_send ))

      if (( ${#error_buf[@]} >= BATCH_SIZE || elapsed >= BATCH_TIMEOUT )); then
        batch=$(printf '%s\n' "${error_buf[@]}")
        PROMPT="These errors just appeared in $LOG_FILE:\n\`\`\`\n$batch\n\`\`\`\nWhat is causing this and how do I fix it?"
        send_to_pane "$SESSION" $PANE "$PROMPT"
        error_buf=()
        last_send=$(date +%s)
      fi
    done
```

---

## 12. Putting it all together — Full agent OS bootstrap

```bash
#!/usr/bin/env bash
# bootstrap-agent-os.sh
# Starts all sessions, injects context, sets up watchers

SESSIONS=("manager" "worker-1" "worker-2" "worker-3")
PROJECT_CONTEXT="You are working on the ackgent.com Multi-LLM Agent OS project built with Zellij and Rust."

echo "=== Bootstrapping Agent OS ==="

# Start all sessions
for session in "${SESSIONS[@]}"; do
  zellij --session "$session" -- claude &
  echo "Started $session"
done

sleep 3  # wait for all claude instances to initialize

# Inject context into each
for session in "${SESSIONS[@]}"; do
  send_to_pane "$session" 0 "$PROJECT_CONTEXT"
  sleep 0.5
done

# Start web server
zellij web --start
echo "Web terminal: https://terminal.ackgent.com:8082"

# Start file watcher in background
bash watch-and-send.sh worker-1 ./src &
echo "File watcher active on ./src → worker-1"

# Start log tailer in background
bash tail-errors.sh manager ./logs/app.log &
echo "Log tailer active → manager"

echo ""
echo "=== Agent OS Running ==="
echo "Sessions: ${SESSIONS[*]}"
echo "Web: https://terminal.ackgent.com:8082"
```
