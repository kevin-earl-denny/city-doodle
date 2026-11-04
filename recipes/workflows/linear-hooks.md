# Linear Hook for Ticket Status on Commit

An opt-in Claude Code hook that moves a Linear ticket to "In Progress" when you commit work for it. It is a safety net: `bin/vibe do CITY-123` already claims the ticket (In Progress, assigned to you), and Linear's native GitHub integration owns every later transition.

## Who Owns Each Transition

| Transition | Owner |
|---|---|
| Todo → In Progress | `bin/vibe do` (and this hook, if a commit lands on an unclaimed ticket) |
| In Progress → In Review | Linear's GitHub integration, when the PR opens |
| In Review → Deployed | Linear's GitHub integration, when the PR merges |
| Deployed → Done | A person or agent, after verifying the change in the running app |

Exactly one system owns each transition. The hook never moves a ticket to Done, never downgrades a ticket that is already started or completed, and never reopens a Canceled or Duplicate ticket.

## Setup

### 1. Add API Key to .env.local

```bash
# .env.local (gitignored)
LINEAR_API_KEY=lin_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get your API key from [Linear Settings → API](https://linear.app/settings/api). Worktrees have no `.env.local`; the hook falls back to the main checkout's copy.

### 2. Copy Example Configuration

```bash
cp .claude/settings.local.json.example .claude/settings.local.json
```

### 3. Verify the Script is Executable

```bash
chmod +x .claude/hooks/linear-update-on-commit.sh
```

## How It Works

After any `git commit` command, the hook:

1. Extracts the first ticket ID from the commit message (pattern `[A-Z]+-[0-9]+`, override with `TICKET_PATTERN` in `.env.local`)
2. Reads the ticket's current state
3. Exits if the state type is started, completed, canceled or duplicate
4. Otherwise moves the ticket to the team's "In Progress" state

It runs asynchronously and exits silently when no API key is configured.

## Troubleshooting

### Hook Not Running

1. Check `.claude/settings.local.json` exists and is valid JSON
2. Verify the script is executable: `ls -la .claude/hooks/`
3. Check Claude Code loaded the hooks (a restart may be needed)

### API Errors

1. Verify `LINEAR_API_KEY` is set in the main checkout's `.env.local`
2. Check the key has write permissions

### Wrong State Names

The hook looks for a state with `type: started` and "progress" in its name, falling back to any started state. If your team uses different names, edit the Python parsing in the script.
