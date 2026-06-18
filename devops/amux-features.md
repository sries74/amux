# amux Feature List

Generated: 2026-06-14
Source: amux-server.py (single-file, ~39,700 lines, ~1.9 MB)

## Overview

amux is a web dashboard and orchestration layer for managing Claude Code (and other AI coding agent) sessions at scale. It wraps tmux-based sessions with a real-time web UI, REST API, SSE event streaming, and fleet-management watchdog loops. It supports 6 AI provider backends and runs on both local and cloud (GCP) environments.

---

## 1. Dashboard UI

### 1.1 Session Cards
- Card-based layout with name, provider badge, model, tags, status, token count
- Status indicators: active (working), waiting (needs input), idle, stopped
- Rate-limit countdown badge
- Steering queue badge
- Provider badge (Claude/Codex/Gemini/Antigravity/Hermes/iTerm2) — click to change
- Model badge — click to change
- YOLO mode indicator
- Pin to top
- Git branch badge with conflict detection
- Inline terminal preview (last 5 intelligible lines)
- Token usage display

### 1.2 Layout Modes
- **Group mode**: sessions grouped by status (Working, Needs Input, Idle, Stopped) — collapsible sections
- **Grid mode**: flat list sorted by activity or alphabetical (desktop >= 900px)
- **List mode**: flat list with drag-and-drop reordering (SortableJS)
- **Tag filtering**: tag bar above sessions, filter by tag on click
- **Search**: text search across session name, dir, desc, tags; matches highlighted in preview

### 1.3 Session Card Interactions
- Expand/collapse card
- Send message textarea (auto-growing, spellcheck)
- Slash-command autocomplete in send input (+ keyboard navigation)
- Card context menu: Peek, Browse files, Info, Pin, Rename, Provider, Model, Description, Tags, Directory, Restart, Stop, Clear scrollback, Duplicate, Clone & continue, New conversation, Share link, Copy mosh command, Archive, Delete
- Double-tap header to peek terminal
- Drag-and-drop to reorder

### 1.4 Terminal Peek
- Modal overlay showing live terminal scrollback (xterm.js)
- Follow mode (auto-scroll to bottom)
- Search within scrollback
- Quick actions: Send, Forward, Return, Esc, Ctrl+C, Ctrl+D
- Steering queue management (add/delete pending messages)
- Tabbed view: Output | Steering | Files | Memory | Info

### 1.5 Session Info Panel
- Session configuration: name, dir, provider, model, flags, description, tags
- Runtime info: PID, CPU%, RSS memory, uptime
- Git info: branch, ahead, dirty files, staged/unstaged diff stats, remote URL
- Board task: current task, task time, session time
- Memory file content
- Session log viewer (with search)
- Slash commands available in this session

### 1.6 File Explorer
- Browse session working directory
- File viewer with syntax highlighting
- Open in IDE button

### 1.7 Command Bar
- Global command input (Ctrl+K / Cmd+K)
- Quick actions: focus, collapse all, create session
- Command history (persisted in SQLite)
- Inline notifications

### 1.8 Settings Panel
- General settings (theme, layout, sort mode, commit guard toggle)
- Default model / provider configuration
- Per-session settings override

### 1.9 Board (Kanban)
- Kanban board view: columns for each status (Backlog, To Do, In Progress, In Review, Done, Verified, Discarded)
- Drag-and-drop status transitions
- Create/edit/delete board items
- Tag system on items
- Due dates with iCal/S3/Google Calendar sync
- Session auto-creation of board issues on agent start
- Auto-complete board issue + pick up next queued task on agent idle
- Claim button for manual task claiming
- Pinned items, position ordering

### 1.10 CRM
- Contact management (name, company, role, email, phone, LinkedIn, Twitter)
- Tag system on contacts
- Interaction logging with date, type, notes
- Follow-up tracking with dates and notes
- Full CRUD API

### 1.11 Notes
- Per-user notes with Quill HTML editor
- Pin notes to top
- Trash (soft delete)
- Version tracking

### 1.12 Journal
- Daily journal entries with text, tags, starred flag
- Photo/media attachments
- Geolocation (lat/lng/place name)
- Customizable daily prompts (prompt1, prompt2, prompt3)
- Full CRUD API

### 1.13 Live Token Analytics
- Per-session: input tokens, output tokens, cache tokens
- Token baseline (snapshot/reset for tracking deltas)
- Daily token usage across all sessions
- Session attribution (amux vs non-amux)

### 1.14 Infrastructure Spend Reports
- GCP billing (JWT auth via service account)
- Anyscale invoices
- Render billing summary
- MongoDB Atlas invoices (Digest auth)
- Qdrant Cloud invoices
- Mixpeek ops server (unified vendor spend: Render, Cloud Run, GKE, Atlas, Qdrant)
- PostHog analytics (active/new users, total events, auth signups, new orgs)
- Chart.js bar charts (daily/weekly/monthly)
- Configurable time periods

### 1.15 System Health Dashboard
- CPU %, RAM usage/disk usage/load avg
- Per-session process attribution (PID, CPU%, RSS, token usage)
- Thread breakdown (main, HTTP, SSE, background)
- Server uptime and request count
- No psutil fallback (subprocess-based)

### 1.16 Graph View
- Knowledge graph with nodes and edges
- Node: label, body, color, folder, position (x/y), pinned
- Edge: source, target, label
- Graphs identified by graph_id
- Full CRUD API

---

## 2. Session Management

### 2.1 Supported Providers
- **Claude Code** (default) — Plan OAuth or API key
- **Codex** (OpenAI) — GPT-5.5 default, sandbox mode
- **Gemini** (deprecated alias, runs via agy)
- **Antigravity (agy)** (Google)
- **Hermes Agent** (Nous Research)
- **iTerm2** (external pane, no start/stop)

### 2.2 Session Lifecycle
- Create session (name, dir, provider, model, flags, description, tags, branch, MCP config)
- Start: spawns tmux session, profiles sourced, /bin/bash → Claude command
- Stop: sends Ctrl+C → respawns shell
- Wake: restarts previously stopped session
- Restart: stop + start (captures log tail before restart for continuity)
- Archive / unarchive
- Delete (soft delete from dashboard, destroy tmux session)
- Block/unblock (blocked-sessions.txt quarantine)
- Duplicate, Clone & continue, New conversation (fresh Claude context)
- Auto-resume on server restart (startup recovery)

### 2.3 Conversation Resume
- Name-based resume (`--name`)
- UUID-based resume (most recent session in project dir)
- Claude `--resume <uuid>` bypasses interactive picker
- Stores cc_session_name, cc_conversation_id in meta
- Session ID conflict auto-restart

### 2.4 Configuration
- Per-session .env file (CC_DIR, CC_DESC, CC_FLAGS, CC_MODEL, CC_TAGS, CC_PINNED, CC_ARCHIVED, CC_AUTO_CONTINUE, CC_AUTO_CONTINUE_MSG, CC_PROVIDER, CC_MCP, CC_BRANCH, CC_WORKTREE, CC_WORKTREE_REPO, CC_RATE_LIMIT_RESUME_TEXT, etc.)
- Global defaults: ~/.amux/defaults.env (CC_DEFAULT_FLAGS)
- Session config PATCH: update dir, desc, flags, provider, model, branch
- Settings UI: change global defaults

### 2.5 Memory (Session Memory)
- Each session has a MEMORY.md file in ~/.amux/memory/
- Global memory (_global.md) composed above a marker
- Syncs to/from Claude's project memory directory
- Changes captured between sessions

### 2.6 Git Integration
- Git branch detection per session
- Branch conflict detection (two sessions on same feature branch)
- Session branch auto-creation (custom git worktree support)
- Commit stamping hook (prepare-commit-msg) — tags commits with $AMUX_SESSION
- Git status: ahead, dirty, unpushed, remote URL
- Unpushed commit count
- Diff viewer (numstat for staged/unstaged/committed changes)

### 2.7 SSH Terminal (PTY)
- Remote terminal sessions (pty.fork)
- xterm.js frontend
- WebSocket for bidirectional I/O
- Resize support

---

## 3. Background Watchdog Loops

### 3.1 YOLO Auto-Responder
- Detects Claude internal safety prompts: "Allow X to...", "Do you want to proceed?", "command contains command substitution..."
- Auto-answers with configured response (1 or 2)
- 6-second cooldown between responses per session
- Runs only when YOLO flags detected in session config
- PostHog event emission

### 3.2 Rate-Limit Watchdog
- Detects /rate-limit-options menu across all sessions
- Auto-selects "Stop and wait for limit to reset" (option 1)
- Parses reset time from scrollback (4 format families + bare-time fallback)
- Schedules auto-resume at reset time
- Per-session daily budget (configurable: off/capped/unlimited)
- 30-second drift tolerance across fleet
- State-aware skip: won't resume if user has moved on
- PostHog event emission

### 3.3 Session Health Monitor (every ~120s per session)
- Proactive auto-compact when context < 50%
- JSONL backup before compaction
- Image dimension limit detection → auto-compact
- Corrupt image detection → auto-compact
- Thinking-block corruption → hard-kill + restart + replay last message
- Session ID conflict → hard-kill + restart + replay
- Auto-continue: unblock sessions waiting for input (CC_AUTO_CONTINUE=1)
- Auto-restart: Claude exited to shell prompt (process-level: OOM/signal 9 detection)
- Stale process reaper: restart sessions with >48h old Claude processes
- Auto-hibernate: stop idle sessions (>30 min) to reclaim memory
- Post-compact continuation
- Session idle event emission (for orchestrator schedules)

### 3.4 Browser Process Reaper
- Idle timeout: 15 minutes
- Hard TTL: 2 hours
- Closes via browser-use CLI
- Hard-kills orphan Chrome processes

### 3.5 Ray Serve Reaper
- Kills Ray Serve clusters running >30 minutes

### 3.6 Cache Eviction
- Git info cache (5 min TTL, 300s max age)
- Model cache (5 min TTL)
- Per-session in-memory dicts pruned for deleted sessions
- Send locks pruned for deleted sessions

---

## 4. Scheduler

### 4.1 Cron Schedules
- Free-text schedule expressions: "every 5m", "every morning", "every weekday at 18:00", "weekly on Monday", "monthly on 15", 5-field cron
- Send message to session tmux
- Run as shell command
- Once / recurring
- Next run calculation
- Run history logging
- UI: create/edit/delete/enable/disable

### 4.2 Event-Triggered Schedules
- Event types: session_idle, board
- Subscribes via trigger_on field
- Debounce + cooldown
- Session allowlist (trigger_sessions)
- Circular self-prevention (own session can't trigger self)

### 4.3 Schedule Watch Mode
- Monitor session output after scheduled command
- Regex done_pattern detection
- Done actions: disable schedule, notify, send follow-up command
- Timeout protection

---

## 5. REST API

### 5.1 Session Endpoints
- GET /api/sessions — list all sessions
- POST /api/sessions — create session
- GET /api/sessions/:name — session detail
- PATCH /api/sessions/:name — update config
- DELETE /api/sessions/:name — delete session (UI token required)
- POST /api/sessions/:name/start
- POST /api/sessions/:name/stop
- POST /api/sessions/:name/wake
- POST /api/sessions/:name/send — send text
- POST /api/sessions/:name/steer — queue steering message
- DELETE /api/sessions/:name/steer — clear steering queue
- POST /api/sessions/:name/config — update model/flags/etc.
- POST /api/sessions/:name/memory — update session memory
- POST /api/sessions/:name/peek — get terminal output (REST fallback)
- GET /api/sessions/:name/git — git info (branch, ahead, dirty, remote)
- POST /api/sessions/:name/git — create session branch
- POST /api/sessions/:name/git — create/switch branch
- POST /api/sessions/:name/peek/clear — clear scrollback
- POST /api/sessions/:name/instructions — set standing instructions
- GET /api/sessions/:name/slash-commands — list available slash commands
- GET /api/sessions/:name/info — full session info
- POST /api/sessions/:name/archive
- POST /api/sessions/:name/share — create share link
- DELETE /api/sessions/:name/share — revoke share link
- POST /api/sessions/:name/claim — claim board task
- GET /api/sessions-git — bulk git info for all sessions

### 5.2 Board Endpoints
- GET /api/board — list items
- POST /api/board — create item
- PATCH /api/board/:id — update item (status, title, desc, tags, due)
- DELETE /api/board/:id — soft delete
- POST /api/board/:id/claim — claim for a session
- POST /api/board/clear-done — delete all done items
- POST /api/board/statuses — create custom status
- PATCH /api/board/statuses/:id — rename status
- DELETE /api/board/statuses/:id — delete status

### 5.3 CRM Endpoints
- GET /api/crm/contacts — list contacts
- POST /api/crm/contacts — create contact
- PATCH /api/crm/contacts/:id — update
- DELETE /api/crm/contacts/:id — soft delete
- POST /api/crm/contacts/:id/interactions — log interaction
- PATCH /api/crm/contacts/:id/interactions/:ix_id — update interaction
- DELETE /api/crm/contacts/:id/interactions/:ix_id
- GET /api/crm/followups — list pending follow-ups

### 5.4 Notes Endpoints
- GET /api/notes — list notes
- GET /api/notes/:path — get note content
- POST /api/notes/:path — create/update note
- DELETE /api/notes/:path — soft delete (trash)
- GET /api/notes-pins — list pinned notes
- POST /api/notes/:path/pin — pin note
- DELETE /api/notes/:path/pin — unpin note

### 5.5 Journal Endpoints
- GET /api/journal — list entries (paginated)
- POST /api/journal — create entry
- GET /api/journal/:id — get entry
- PATCH /api/journal/:id — update entry
- DELETE /api/journal/:id — soft delete
- POST /api/journal/:id/media — upload media
- DELETE /api/journal/:id/media/:mid — delete media

### 5.6 Schedule Endpoints
- GET /api/schedules — list schedules
- POST /api/schedules — create schedule
- PATCH /api/schedules/:id — update schedule
- DELETE /api/schedules/:id — soft delete
- POST /api/schedules/:id/run — manual run
- GET /api/schedules/:id/runs — run history

### 5.7 Memory Endpoints
- GET /api/memory/global — get global memory
- POST /api/memory/global — update global memory
- GET /api/sessions/:name/memory — get session memory
- POST /api/sessions/:name/memory — update session memory

### 5.8 Reports Endpoints
- GET /api/reports — list saved reports
- POST /api/reports — create report
- PATCH /api/reports/:id — update
- DELETE /api/reports/:id
- GET /api/reports/types — list available report types (infra-spend, mixpeek-vendor-spend, posthog-analytics)
- POST /api/reports/:id/refresh — fetch fresh data

### 5.9 Settings / Config Endpoints
- GET /api/settings — get all settings
- PATCH /api/settings — update settings (default model, provider, etc.)
- POST /api/settings/default-model — set default model
- POST /api/settings/default-provider — set default provider

### 5.10 System Endpoints
- GET /api/system/metrics — CPU, RAM, disk, per-session stats
- GET /api/system/info — server info, uptime, version
- GET /api/tokens/daily — token usage for today
- POST /api/tokens/baseline — set token baseline
- GET /api/event-log — recent event log (SSE + structured)
- GET /api/health — health check

### 5.11 Auth Endpoints
- POST /api/auth/login — token-based auth
- GET /api/auth/verify — verify token

### 5.12 Misc Endpoints
- GET /api/calendar.ics — iCal feed of board due dates
- POST /api/uploads — file upload (20 MB max)
- POST /api/fs/upload — drag-and-drop file upload
- DELETE /api/fs/delete — file deletion (sensitive path blocked)
- GET /api/branding/:file — white-label assets (icon, logo)
- POST /api/pull — git pull
- GET /api/release-notes — release notes
- GET /sw.js — service worker
- GET /manifest.json — PWA manifest
- GET /icon.svg, /icon.png, /icon-192.png, /icon-512.png — PWA icons

---

## 6. Real-Time Features

### 6.1 SSE (Server-Sent Events)
- Live session updates (status, preview, tokens, task)
- Live system metrics streaming
- Real-time notifications/alerts
- Board updates
- Cache-invalidation triggers (2s TTL)

### 6.2 WebSocket
- Terminal PTY (xterm.js) for session peek
- Remote SSH terminal

---

## 7. CLI Stub (/usr/local/bin/amux)

Board commands: add, list, done/doing/todo/reset
CRM commands: add, update, get, log, followups, list
Session commands: list, restart, share, unshare
Help

---

## 8. Security

- Token-based authentication (AMUX_AUTH_TOKEN)
- UI token (X-Amux-UI-Token) for destructive API calls — prevents sessions from deleting other sessions
- Shell injection prevention: shlex.quote on all flags, re-quoting at spawn time
- API key redaction in piped logs (pipe-pane Python redactor)
- Model name validator (regex, no leading hyphen, max 255 chars)
- Path traversal prevention (note paths, file API)
- Sensitive directory blocklist (.ssh, .gnupg, .aws, etc.)
- Session name regex validation
- Atomic secure writes for .env files (tempfile + fsync + rename, mode 0o600)

---

## 9. Deployment & Ops

### 9.1 Single Binary
- Single Python file (~1.9 MB) + inline HTML/CSS/JS
- SQLite database (auto-creates on first run)
- No Docker required for local dev

### 9.2 Cloud (GCP)
- cloud/ directory with Terraform + setup script
- Docker container run
- AMUX_PORT env var triggers cloud mode (creates hello-world session)

### 9.3 Auto-Restart
- Server watches its own mtime for auto-reload
- os.execv self-restart preserves tmux sessions
- Log pipe-pane re-attached on restart
- Dead session log captured before swaps

### 9.4 Idempotent Migrations
- Board items.json → SQLite (one-time)
- Skills .md files → SQLite (one-time)
- Flat memory files → session-keyed memory (one-time)
- Schema migrations via ALTER TABLE on startup

---

## 10. Built-in Templates

- Software Project (src/, docs/, tests/)
- Fitness & Health Tracker (workouts/, nutrition/, progress/)
- Research & Analysis (findings/, data/, summaries/)
- Personal / Life Admin (projects/, planning/, finances/)
- Content & Marketing (drafts/, media/, calendar/)

---

## 11. Email Integration (Gmail OAuth)

- Gmail account linking via OAuth tokens
- Email event extraction → calendar events
- Per-account sync
- Token refresh
- Stored in SQLite (email_accounts, email_events tables)

---

## 12. Multi-Organization

- Org table (name, created_at)
- Org members (email, name, role, joined_at)
- Org invites (token, email, expiry)
- Waitlist (email, note, timestamp)

---

## 13. Preferences & Layout

- Layout presets (hidden panes, tab order)
- User preferences (key-value: sort mode, commit guard, auto-compact, etc.)
- Per-browser UI state in localStorage

---

## 14. Session Pipeline (Agent Orchestration)

- Standing instructions (re-sent on restart, survives compaction)
- Steering queue (batch message delivery)
- Board task auto-pickup on agent idle
- Commit guard (nudges agent to commit dirty work on idle)
- Closed-loop orchestrator events (session_idle, board)
- Post-compact continue message

---

## 15. Torrent (aria2c)

- aria2c JSON-RPC integration
- Start/stop daemon
- List active/waiting/stopped torrents
- Download directory: ~/Downloads/amux-torrents

---

## 16. Browser Automation

- browser-use CLI integration
- Per-session serialized locks (no concurrent Chromium)
- Screenshot capability (retries on SessionManager errors)
- Agent loop (Anthropic Computer Use API)
- Idle browser reaper

---

## 17. Auto-Configuration

- ~/.claude.json: onboarding wizard skipped, API key approved, default workspaces trusted
- ~/.claude/settings.json: YOLO mode + auto-accept permissions
- ~/.codex/config.toml: auto-trust projects
- ~/.claude/commands/: skills synced from SQLite
- Git profile sourced in tmux

---

## 18. Event Log

- In-memory ring buffer (2,000 events)
- Typed events: session, board, memory, file, system, http, mails
- Client IP + session + status enrichment
- Downgraded to http on 4xx/5xx

---

## 19. Request ID / Correlation

- Per-request UUID (req_id) for end-to-end tracing
- Thread-local storage for req enrichment

---

## 20. Deferred Handler Registry

- Register HTTP handlers that trigger on specific requests (deferred_actions)
- Auto-cleanup on session deletion or new session creation
- Timeout protection (10s cleanup cycle)
