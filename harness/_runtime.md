# Runtime -- Global Policy

This is the runtime layer of the Natural Language Agent Harness (NLAH).
It defines session lifecycle, git workflow, tool routing, and default behaviors
that apply regardless of which task skill is active.

---

## Git workflow

- Push directly to `main` for all changes unless explicitly asked otherwise.
- Use feature branches when the user requests them or for risky changes.

## Session startup

At the start of every conversation:

1. **Load state** -- read your session handoff file to resume context.
2. **Check for loops** -- run `git log --oneline -15` and scan for repeated
   commits touching the same file. If any file appears 3+ times in recent
   history, flag it and re-read from scratch before further work.
3. **Run tests** -- `python -m pytest tests/ -q` and include pass/fail in
   the status report. Treat failures as blockers before touching other code.
4. **Capability smoke tests** -- run whatever smoke tests are relevant to
   your agent's integrations. Include pass/fail in status report.
5. **Open with status report:**
   ```
   **Status check**
   Done last session: <1-3 bullets>
   In progress: <what was mid-flight, if anything>
   Up next: <what user confirmed to do next>
   Loop detected (if applicable): <file + pattern>
   ```

Do not wait for the user to ask. Do not skip this even if the first message
seems urgent.

## Session end

Before the conversation closes, update your session handoff file with:
- What was completed this session
- What is unfinished or blocked
- What the user said to do next

## Mid-session handoff updates

Update your handoff file after every push, not just at session close.
A stale handoff means jarring context loss after compaction or restart.

## Default to action (MANDATORY)

**The default is execution, not proposal.** Unless an action is genuinely
destructive or irreversible, just do it.

- Non-destructive code changes: read, fix, verify, push. No permission needed.
- If the user has already pushed in a direction, that's a standing green light
  for that class of action this session.
- Reserve confirmation for: destructive operations, external side effects, or
  genuinely ambiguous intent.

## Tool use narration

Before every tool call, write a brief sentence explaining what file/resource
you're reading and why. Never invoke a tool silently.

## Tool routing

<!-- Customize this section for your agent's specific tools.

Example:
- For web fetching: ALWAYS use `your_mcp_browse_tool`, NEVER use `WebFetch`
- For web search: ALWAYS use `your_mcp_search_tool`, NEVER use `WebSearch`

The key principle: if you have MCP tools or custom tools that bypass
permission prompts, always prefer those over built-in tools that trigger
permission dialogs.
-->

## Known API quirks

<!-- Document API quirks you discover here. Examples:
- API X silently ignores parameter Y -- filter in Python after fetching
- Never use `pkill -f` -- matches full command lines including the CLI subprocess
-->
