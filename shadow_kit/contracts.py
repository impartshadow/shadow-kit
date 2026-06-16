"""
contracts.py -- Code-enforced NLAH contracts for Shadow Kit.

Each contract is a pre/post condition that can be checked against a response
or action context. Contracts are the enforcement layer that makes harness
rules deterministic rather than relying on prompt compliance.

Usage:
    from shadow_kit.contracts import check_all_pre, check_all_post

    # Before an action:
    violations = check_all_pre(context)
    if violations:
        # Handle violations -- block or warn

    # After generating a response:
    violations = check_all_post(context, response)
    if violations:
        # Inject warnings or block the response

Contracts reference: harness/contracts/*.md
Failure taxonomy: harness/failure_modes/taxonomy.md
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ContractContext:
    """Context passed to contract checks.

    Populate this with information about the current action/response before
    running contract checks. Fields you don't use can be left at defaults.
    """
    action: str = ""                    # e.g. "git_push", "send_email", "respond"
    action_params: dict = field(default_factory=dict)  # parameters for the action
    response_text: str = ""             # the outgoing response text
    verification_output: str = ""       # captured verification command output
    preview_shown: bool = False         # whether a preview was displayed before action
    smoke_test_ran: bool = False        # whether a capability smoke test was run
    files_read: list[str] = field(default_factory=list)  # files read this interaction
    files_edited: list[str] = field(default_factory=list)  # files edited this interaction
    commits_this_session: dict[str, int] = field(default_factory=dict)  # file -> commit count
    tool_calls: list[str] = field(default_factory=list)  # tool names called this interaction
    tool_params: list[dict] = field(default_factory=list)  # params for each tool call


@dataclass
class Violation:
    """A contract violation."""
    contract: str           # contract name (e.g. "verify-before-push")
    failure_mode: str       # taxonomy code (e.g. "FM-002")
    message: str            # human-readable description
    severity: str = "warn"  # "warn" or "block"
    recovery: str = ""      # suggested recovery action


# ---------------------------------------------------------------------------
# Shared text-stripping utility
# ---------------------------------------------------------------------------


def _strip_non_action_text(text: str) -> str:
    """Remove code blocks, inline code, blockquotes, tables, and meta-discussion.

    Used by multiple contracts to prevent false positives when the response
    is discussing specs, fixes, or contract behavior rather than performing actions.
    """
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"^>\s*.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\|.*\|.*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"^.*(?:contract|FM-\d{3}|failure.mode|violation|guard|taxonomy|false.positiv|"
        r"spec|fix(?:es|ed|ing)?.*(?:detect|pattern|trigger|fire)|"
        r"(?:pre|post).check|severity).*$",
        "", text, flags=re.MULTILINE | re.IGNORECASE,
    )
    return text


# ---------------------------------------------------------------------------
# Base contract class
# ---------------------------------------------------------------------------


class Contract:
    """Base class for all contracts.

    Subclass this to create new contracts. Override check_pre() for
    precondition checks (before an action) and check_post() for
    postcondition checks (after a response is generated).

    Set `name` and `failure_mode` as class attributes. Toggle `enabled`
    at runtime to disable a contract without removing it.
    """
    name: str = "base"
    failure_mode: str = "FM-000"
    enabled: bool = True

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        """Check preconditions before an action. Return Violation or None."""
        return None

    def check_post(self, ctx: ContractContext) -> Optional[Violation]:
        """Check postconditions after a response is generated. Return Violation or None."""
        return None

    def auto_recover(self, ctx: ContractContext, violation: Violation) -> Optional[str]:
        """Attempt automatic recovery. Returns corrected response text, or None.

        Override in subclasses that support auto-recovery. This is the
        corrective feedback loop: instead of just blocking and waiting for
        the next turn, the contract can rewrite the response.
        """
        return None


# ---------------------------------------------------------------------------
# Built-in contracts
# ---------------------------------------------------------------------------


class VerifyBeforePush(Contract):
    """FM-002: Block git push if no verification output is present.

    Catches the pattern where the agent says "Done." without actually
    running a verification command. Mental verification is not verification.
    """
    name = "verify-before-push"
    failure_mode = "FM-002"

    _VERIFICATION_MARKERS = [
        r"passed",
        r"PASSED",
        r"\d+ passed",
        r"OK$",
        r"ok\b",
        r"^\s*\{",       # JSON output
        r"^\s*\[",       # list output
        r"Traceback",    # even failure output counts -- it means the command ran
    ]

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "git_push":
            return None

        if not ctx.files_edited:
            return None

        if ctx.verification_output:
            return None

        for pattern in self._VERIFICATION_MARKERS:
            if re.search(pattern, ctx.response_text, re.MULTILINE):
                return None

        return Violation(
            contract=self.name,
            failure_mode=self.failure_mode,
            message="Push attempted without verification output. Run the appropriate "
                    "verification command and paste the output before pushing.",
            severity="block",
            recovery="Run your verification command (tests, linter, dry-run), "
                     "paste the output, then push.",
        )


class PreDenialGate(Contract):
    """FM-001: Block denial responses that haven't run a smoke test.

    Catches the pattern where the agent says "I can't access X" without
    actually trying the command. The LLM tendency is to hedge -- this
    contract forces it to attempt the action first.
    """
    name = "pre-denial-gate"
    failure_mode = "FM-001"

    _DENIAL_PATTERNS = [
        r"\bi\s+(?:can't|cannot|don't|do not)\s+(?:access|fetch|pull|grab|browse|retrieve|read|open|reach)\b",
        r"\bi\s+(?:am\s+)?(?:not\s+able|unable)\s+to\s+(?:access|fetch|pull|browse|retrieve)\b",
        r"\bi\s+(?:don't|do not)\s+have\s+(?:access|permission)\b",
        r"\bnot\s+possible\s+from\s+here\b",
        r"\bno\s+way\s+(?:for\s+me\s+)?to\s+access\b",
        r"\bneed\s+(?:your\s+)?permission\s+to\s+(?:access|fetch|pull|browse)\b",
        r"\bcould\s+you\s+(?:grant|give|allow)\s+(?:me\s+)?(?:access|permission)\b",
        r"\bgrant\s+me\s+access\b",
    ]

    def check_post(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "respond":
            return None

        text = _strip_non_action_text(ctx.response_text)
        has_denial = any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in self._DENIAL_PATTERNS
        )
        if not has_denial:
            return None

        if ctx.smoke_test_ran:
            return None

        if ctx.tool_calls:
            return None

        has_output = bool(re.search(
            r"```[\s\S]*?(Error|OK|Traceback|output|result)", ctx.response_text
        ))
        if has_output:
            return None

        return Violation(
            contract=self.name,
            failure_mode=self.failure_mode,
            message="Denial without smoke test. Before claiming something is inaccessible, "
                    "run the actual command and show the output.",
            severity="block",
            recovery="Try every available path for the resource. Run a smoke test. "
                     "Show output. Then decide.",
        )


class LoopTripwire(Contract):
    """FM-003: Warn/block on 3+ commits to the same file.

    Catches the edit loop pattern where the agent keeps patching the same
    file instead of re-reading it and understanding the root cause.
    """
    name = "loop-tripwire"
    failure_mode = "FM-003"

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action not in ("git_push", "edit_file"):
            return None

        for filepath, count in ctx.commits_this_session.items():
            if count >= 3:
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Loop detected: {filepath} has been committed {count} times "
                            f"this session. Re-read the entire file before touching it again.",
                    severity="block" if count >= 4 else "warn",
                    recovery="Re-read the entire file from scratch. Trace the logic. "
                             "Understand why previous attempts failed. One fix, verified.",
                )
        return None


class ReadBeforeEdit(Contract):
    """FM-003 (variant): Flag edits to files that weren't read first.

    Memory of code from earlier in a conversation is not reliable.
    Always re-read before editing.
    """
    name = "read-before-edit"
    failure_mode = "FM-003"

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "edit_file":
            return None

        for filepath in ctx.files_edited:
            if filepath not in ctx.files_read:
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Editing {filepath} without reading it first. "
                            f"Memory of code is not reliable.",
                    severity="warn",
                    recovery=f"Read {filepath} in full before editing.",
                )
        return None


class ActionDeferralGuard(Contract):
    """FM-011: Detect responses that propose/instruct instead of executing.

    Catches two sub-patterns:
      (a) Deferred action -- "would you like me to", "I can set up", "here's the approach"
      (b) Manual instruction -- "go to settings", "click on X", "navigate to"

    Fires when 2+ markers appear without evidence of actual execution
    (tool calls, past-tense completion markers, or discussion-mode context).
    """
    name = "action-deferral-guard"
    failure_mode = "FM-011"

    # Override this set with your agent's execution tools
    EXECUTION_TOOLS: set[str] = {
        "Write", "Edit", "NotebookEdit", "Bash",
    }

    _CLASS_A_PATTERNS = [
        re.compile(r"\bwould you like me to\b", re.IGNORECASE),
        re.compile(r"\bwant me to\b", re.IGNORECASE),
        re.compile(r"\bshall I\b", re.IGNORECASE),
        re.compile(r"\bI can (?:set up|configure|create|build|wire|write|implement|send|schedule|deploy)\b", re.IGNORECASE),
        re.compile(r"\bI'll (?:go ahead and|set up|create|send|configure|wire|write)\b", re.IGNORECASE),
        re.compile(r"\blet me know if you(?:'d like| want)\b", re.IGNORECASE),
        re.compile(r"\bhere'?s (?:the |my |an? )?(?:approach|plan|strategy|architecture)\b", re.IGNORECASE),
        re.compile(r"\bthe approach (?:would be|is to)\b", re.IGNORECASE),
        re.compile(r"\bsteps?\s*(?:\d|:)", re.IGNORECASE),
    ]

    _CLASS_B_PATTERNS = [
        re.compile(r"\bgo to (?:settings|preferences|configuration|the .+ page)\b", re.IGNORECASE),
        re.compile(r"\bclick (?:on )?(?:the |your )?['\"\u201c].+['\"\u201d]", re.IGNORECASE),
        re.compile(r"\bnavigate to\b", re.IGNORECASE),
        re.compile(r"\bopen (?:the |your )?(?:settings|preferences|dashboard|portal|console)\b", re.IGNORECASE),
        re.compile(r"(?:\u2192|->)\s*\w+\s*(?:\u2192|->)\s*\w+", re.IGNORECASE),
        re.compile(r"\bselect ['\"\u201c].+['\"\u201d] from\b", re.IGNORECASE),
        re.compile(r"\bright-click\b", re.IGNORECASE),
        re.compile(r"\byou(?:'ll| will) need to\b", re.IGNORECASE),
        re.compile(r"\byou can (?:go to|open|click|navigate|visit)\b", re.IGNORECASE),
    ]

    _PAST_TENSE_MARKERS = [
        re.compile(r"\bDone[.\s\u2014]", re.IGNORECASE),
        re.compile(r"\bpushed\b", re.IGNORECASE),
        re.compile(r"\bcommitted\b", re.IGNORECASE),
        re.compile(r"\bdeployed\b", re.IGNORECASE),
        re.compile(r"\bcreated\b", re.IGNORECASE),
        re.compile(r"\bsent the\b", re.IGNORECASE),
        re.compile(r"\bscheduled\b", re.IGNORECASE),
        re.compile(r"\bwrote\b", re.IGNORECASE),
    ]

    _DISCUSSION_MARKERS = [
        re.compile(r"\bbrainstorm", re.IGNORECASE),
        re.compile(r"\bjust thinking\b", re.IGNORECASE),
        re.compile(r"\bno code changes\b", re.IGNORECASE),
    ]

    _BLOCKER_MARKERS = [
        re.compile(r"\bblocked by\b", re.IGNORECASE),
        re.compile(r"\berror:\b", re.IGNORECASE),
        re.compile(r"\bfailed:\b", re.IGNORECASE),
    ]

    def check_post(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "respond":
            return None

        text = ctx.response_text

        if any(p.search(text) for p in self._DISCUSSION_MARKERS):
            return None

        user_msg = ctx.action_params.get("user_message", "")
        if re.match(r"(?:how would|what if|what would)\b", user_msg, re.IGNORECASE):
            return None

        if any(t in self.EXECUTION_TOOLS for t in ctx.tool_calls):
            return None

        if any(p.search(text) for p in self._PAST_TENSE_MARKERS):
            return None

        if any(p.search(text) for p in self._BLOCKER_MARKERS):
            return None

        stripped = _strip_non_action_text(text)

        a_matches = sum(1 for p in self._CLASS_A_PATTERNS if p.search(stripped))
        b_matches = sum(1 for p in self._CLASS_B_PATTERNS if p.search(stripped))
        total = a_matches + b_matches

        if total < 2:
            return None

        if a_matches > b_matches:
            msg = ("Response proposes an action without executing it. "
                   "Default to action -- do the thing, don't offer to do it.")
        elif b_matches > a_matches:
            msg = ("Response gives manual instructions instead of solving "
                   "programmatically. Use APIs and tools first.")
        else:
            msg = ("Response explains/proposes instead of executing. "
                   "Do the thing, don't describe doing it.")

        return Violation(
            contract=self.name,
            failure_mode=self.failure_mode,
            message=msg,
            severity="block",
            recovery="Execute the action directly. If a tool exists for it, call "
                     "the tool. Only explain if execution genuinely failed -- "
                     "and in that case, show the error output.",
        )


class TopicOverrunGuard(Contract):
    """FM-013: Detect when the agent continues on a topic after the user signals closure.

    Catches the pattern where the user says "done" or "that's fine" and the
    agent keeps going with "one more thing" or "also, while we're at it."
    """
    name = "topic-overrun-guard"
    failure_mode = "FM-013"

    _OVERRUN_PATTERNS = [
        re.compile(
            r"(?:you (?:said|mentioned) .{0,30}(?:done|fine|good|set|saved|already)|"
            r"(?:got it|understood|noted).{0,30}(?:but|however|also|one more|additionally))",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:since you|while you|before you go|one (?:more|last) thing)",
            re.IGNORECASE,
        ),
    ]

    def check_post(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "respond":
            return None

        text = ctx.response_text
        for pattern in self._OVERRUN_PATTERNS:
            if pattern.search(text):
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message="Response continues a topic after the user signaled closure. "
                            "When they say done/fine/good -- move on.",
                    severity="warn",
                    recovery="Drop the current thread. If there's genuinely urgent "
                             "follow-up, save it for later.",
                )
        return None


class CompletionIntegrity(Contract):
    """FM-014: Catch premature completion claims when gaps are acknowledged.

    Fires when a response claims something is "done", "shipped", etc.
    but also contains language acknowledging unresolved gaps. The pattern:
    saying "shipped" in the opening then listing "not done" items means
    the deliverable doesn't match the claim.
    """
    name = "completion-integrity"
    failure_mode = "FM-014"

    _COMPLETION_PATTERNS = [
        re.compile(r"\b(?:all\s+three|all\s+\d+)\s+(?:are\s+)?(?:shipped|done|wired|live|deployed)\b", re.IGNORECASE),
        re.compile(r"\bshipped\s+and\s+wired\b", re.IGNORECASE),
        re.compile(r"\b(?:everything|all)\s+(?:is\s+)?(?:done|shipped|wired|live|complete|deployed)\b", re.IGNORECASE),
        re.compile(r"^(?:Done|Shipped|Wired|Deployed|Complete)[.\s\u2014]", re.MULTILINE),
    ]

    _GAP_PATTERNS = [
        re.compile(r"\bnot\s+done\b", re.IGNORECASE),
        re.compile(r"\bstill\s+missing\b", re.IGNORECASE),
        re.compile(r"\bstill\s+broken\b", re.IGNORECASE),
        re.compile(r"\bgap[s]?\s+(?:from|in|remain|I)\b", re.IGNORECASE),
        re.compile(r"\bnot\s+(?:yet\s+)?(?:wired|implemented|built|connected|integrated)\b", re.IGNORECASE),
        re.compile(r"\b(?:hasn't|has not)\s+been\s+(?:wired|implemented|built|done)\b", re.IGNORECASE),
        re.compile(r"\bhalf[- ]done\b", re.IGNORECASE),
        re.compile(r"\bpartially\b", re.IGNORECASE),
        re.compile(r"\b(?:what's\s+)?NOT\s+done\b"),  # case-sensitive -- intentional caps
    ]

    _AUDIT_PATTERNS = [
        re.compile(r"\baudit\b", re.IGNORECASE),
        re.compile(r"\bhonest\s+(?:assessment|status|audit)\b", re.IGNORECASE),
        re.compile(r"\bverdict\b", re.IGNORECASE),
    ]

    def check_post(self, ctx: ContractContext) -> Optional[Violation]:
        if ctx.action != "respond":
            return None

        text = ctx.response_text

        if any(p.search(text) for p in self._AUDIT_PATTERNS):
            return None

        has_completion = any(p.search(text) for p in self._COMPLETION_PATTERNS)
        if not has_completion:
            return None

        gap_count = sum(1 for p in self._GAP_PATTERNS if p.search(text))
        if gap_count < 2:
            return None

        return Violation(
            contract=self.name,
            failure_mode=self.failure_mode,
            message=f"Response claims completion but acknowledges {gap_count} gaps. "
                    "Don't say 'done' when gaps remain.",
            severity="block",
            recovery="Remove the completion claim. Lead with what's actually done, "
                     "then list what's remaining.",
        )


class GitPushTargetGuard(Contract):
    """FM-015: Validate git push parameters.

    Blocks force-pushes to protected branches and warns on pushes to
    unexpected remotes. Parses git push commands from tool call parameters.
    """
    name = "git-push-target-guard"
    failure_mode = "FM-015"

    _PROTECTED_BRANCHES = {"main", "master", "production", "release"}
    _FORCE_FLAGS = {"--force", "-f", "--force-with-lease"}

    def _parse_git_push(self, command: str) -> dict | None:
        """Extract push parameters from a shell command string."""
        m = re.search(r"git\s+push\b(.*?)(?:[&;|]|$)", command)
        if not m:
            return None
        rest = m.group(1).split()
        flags = set()
        positional = []
        for token in rest:
            if token.startswith("-"):
                flags.add(token)
            else:
                positional.append(token)
        remote = positional[0] if len(positional) >= 1 else "origin"
        refspec = positional[1] if len(positional) >= 2 else ""
        branch = refspec.split(":")[0] if refspec else ""
        return {
            "branch": branch,
            "remote": remote,
            "force": bool(flags & self._FORCE_FLAGS),
        }

    def _get_push_params(self, ctx: ContractContext) -> list[dict]:
        results = []
        if ctx.action_params and ctx.action_params.get("branch"):
            results.append(ctx.action_params)
        for tool_name, params in zip(ctx.tool_calls, ctx.tool_params):
            if tool_name not in ("Bash", "run_shell"):
                continue
            cmd = params.get("command", "")
            parsed = self._parse_git_push(cmd)
            if parsed:
                results.append(parsed)
        return results

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        push_params_list = self._get_push_params(ctx)
        if not push_params_list:
            if ctx.action != "git_push":
                return None
            return None

        for params in push_params_list:
            branch = params.get("branch", "").strip()
            force = params.get("force", False)
            remote = params.get("remote", "origin")

            if force and branch in self._PROTECTED_BRANCHES:
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Force push to protected branch '{branch}' blocked.",
                    severity="block",
                    recovery="Push to a feature branch instead, or remove --force.",
                )

            if force:
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Force push to '{branch or 'current branch'}' detected.",
                    severity="warn",
                    recovery="Confirm force push is needed. Prefer normal push.",
                )

            if remote not in ("origin", ""):
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Push to non-origin remote '{remote}'.",
                    severity="warn",
                    recovery=f"Confirm the remote '{remote}' is correct.",
                )

        return None


class DangerousPathGuard(Contract):
    """FM-017: Block writes to sensitive file paths.

    Prevents accidental writes to .env, credential files, SSH keys, etc.
    Configure the project root to get warnings for out-of-project writes.
    """
    name = "dangerous-path-guard"
    failure_mode = "FM-017"

    _SENSITIVE_PATTERNS = [
        re.compile(r"\.env$"),
        re.compile(r"credentials?\.json$"),
        re.compile(r"token\.json$"),
        re.compile(r"\.ssh/"),
        re.compile(r"\.gnupg/"),
        re.compile(r"/etc/"),
        re.compile(r"\.git/config$"),
    ]

    # Override this in your subclass or set it after instantiation
    project_root: str = ""

    def check_pre(self, ctx: ContractContext) -> Optional[Violation]:
        for tool_name, params in zip(ctx.tool_calls, ctx.tool_params):
            if tool_name not in ("Write", "write_file", "Edit"):
                continue

            path = params.get("file_path") or params.get("path", "")
            if not path:
                continue

            for pattern in self._SENSITIVE_PATTERNS:
                if pattern.search(path):
                    return Violation(
                        contract=self.name,
                        failure_mode=self.failure_mode,
                        message=f"Write to sensitive path '{path}' blocked.",
                        severity="block",
                        recovery="Don't write directly to credential/config files. "
                                 "Use a secrets manager for credentials.",
                    )

            if self.project_root and not path.startswith(self.project_root):
                return Violation(
                    contract=self.name,
                    failure_mode=self.failure_mode,
                    message=f"Write to '{path}' is outside the project directory.",
                    severity="warn",
                    recovery=f"Verify the path is correct. Prefer writing within "
                             f"{self.project_root}.",
                )

        return None


# ---------------------------------------------------------------------------
# Runtime governance -- violation metrics and contract health
# ---------------------------------------------------------------------------


class ContractGovernor:
    """Runtime governance layer for the contract system.

    Tracks violation counts, contract error rates, auto-recovery success
    rates, and provides metrics for monitoring and self-improvement.
    """

    def __init__(self):
        self._violation_log: list[dict] = []
        self._error_log: list[dict] = []
        self._recovery_log: list[dict] = []

    def record_violation(self, violation: Violation) -> None:
        """Record a violation for metrics."""
        import time
        self._violation_log.append({
            "contract": violation.contract,
            "failure_mode": violation.failure_mode,
            "severity": violation.severity,
            "ts": time.time(),
        })

    def record_error(self, contract_name: str, error: str) -> None:
        """Record a contract that crashed during check."""
        import time
        self._error_log.append({
            "contract": contract_name,
            "error": error,
            "ts": time.time(),
        })

    def record_recovery(self, contract_name: str, success: bool) -> None:
        """Record an auto-recovery attempt."""
        import time
        self._recovery_log.append({
            "contract": contract_name,
            "success": success,
            "ts": time.time(),
        })

    def get_metrics(self) -> dict:
        """Return governance metrics summary."""
        import time
        now = time.time()
        hour_ago = now - 3600

        violation_counts: dict[str, int] = {}
        recent_violations: dict[str, int] = {}
        for v in self._violation_log:
            name = v["contract"]
            violation_counts[name] = violation_counts.get(name, 0) + 1
            if v["ts"] > hour_ago:
                recent_violations[name] = recent_violations.get(name, 0) + 1

        error_counts: dict[str, int] = {}
        for e in self._error_log:
            name = e["contract"]
            error_counts[name] = error_counts.get(name, 0) + 1

        recovery_attempts = len(self._recovery_log)
        recovery_successes = sum(1 for r in self._recovery_log if r["success"])

        return {
            "total_violations": len(self._violation_log),
            "violations_last_hour": sum(recent_violations.values()),
            "violations_by_contract": violation_counts,
            "recent_violations_by_contract": recent_violations,
            "contract_errors": error_counts,
            "recovery_attempts": recovery_attempts,
            "recovery_successes": recovery_successes,
            "recovery_rate": (recovery_successes / recovery_attempts * 100)
                if recovery_attempts > 0 else 0.0,
            "active_contracts": len([c for c in _ALL_CONTRACTS if c.enabled]),
            "disabled_contracts": [c.name for c in _ALL_CONTRACTS if not c.enabled],
        }

    def get_hot_contracts(self, window_seconds: int = 3600, threshold: int = 3) -> list[str]:
        """Return contracts firing too frequently (possible misconfiguration)."""
        import time
        cutoff = time.time() - window_seconds
        counts: dict[str, int] = {}
        for v in self._violation_log:
            if v["ts"] > cutoff:
                counts[v["contract"]] = counts.get(v["contract"], 0) + 1
        return [name for name, count in counts.items() if count >= threshold]


# Singleton governor instance
_governor = ContractGovernor()


def get_governor() -> ContractGovernor:
    """Get the singleton ContractGovernor."""
    return _governor


# ---------------------------------------------------------------------------
# Registry and bulk check
# ---------------------------------------------------------------------------

_ALL_CONTRACTS: list[Contract] = [
    VerifyBeforePush(),
    PreDenialGate(),
    LoopTripwire(),
    ReadBeforeEdit(),
    ActionDeferralGuard(),
    TopicOverrunGuard(),
    CompletionIntegrity(),
    GitPushTargetGuard(),
    DangerousPathGuard(),
]


def check_all_pre(ctx: ContractContext) -> list[Violation]:
    """Run all contract precondition checks. Returns list of violations."""
    violations = []
    governor = get_governor()
    for contract in _ALL_CONTRACTS:
        if not contract.enabled:
            continue
        try:
            v = contract.check_pre(ctx)
            if v:
                violations.append(v)
                governor.record_violation(v)
                logger.warning(
                    f"[contracts] PRE violation: {v.contract} ({v.failure_mode}) -- {v.message}"
                )
        except Exception as exc:
            governor.record_error(contract.name, str(exc))
            logger.error(f"[contracts] {contract.name}.check_pre crashed: {exc}")
    return violations


def check_all_post(ctx: ContractContext) -> list[Violation]:
    """Run all contract postcondition checks. Returns list of violations."""
    violations = []
    governor = get_governor()
    for contract in _ALL_CONTRACTS:
        if not contract.enabled:
            continue
        try:
            v = contract.check_post(ctx)
            if v:
                violations.append(v)
                governor.record_violation(v)
                logger.warning(
                    f"[contracts] POST violation: {v.contract} ({v.failure_mode}) -- {v.message}"
                )
        except Exception as exc:
            governor.record_error(contract.name, str(exc))
            logger.error(f"[contracts] {contract.name}.check_post crashed: {exc}")
    return violations


def attempt_auto_recovery(ctx: ContractContext, violations: list[Violation]) -> Optional[str]:
    """Attempt auto-recovery for violations. Returns corrected response text,
    or None if no recovery was possible."""
    governor = get_governor()
    for v in violations:
        contract = get_contract(v.contract)
        if contract is None:
            continue
        try:
            recovered = contract.auto_recover(ctx, v)
            if recovered is not None:
                governor.record_recovery(v.contract, success=True)
                logger.info(f"[contracts] auto-recovered {v.contract}: response rewritten")
                return recovered
            governor.record_recovery(v.contract, success=False)
        except Exception as exc:
            governor.record_error(v.contract, f"auto_recover crashed: {exc}")
            logger.error(f"[contracts] {v.contract}.auto_recover crashed: {exc}")
    return None


def get_contract(name: str) -> Optional[Contract]:
    """Look up a contract by name."""
    for c in _ALL_CONTRACTS:
        if c.name == name:
            return c
    return None


def register_contract(contract: Contract) -> None:
    """Dynamically register a new contract. Replaces any existing contract with the same name."""
    _ALL_CONTRACTS[:] = [c for c in _ALL_CONTRACTS if c.name != contract.name]
    _ALL_CONTRACTS.append(contract)
    logger.info(f"[contracts] registered: {contract.name} ({contract.failure_mode})")


def list_contracts() -> list[dict]:
    """Return summary of all registered contracts."""
    return [
        {
            "name": c.name,
            "failure_mode": c.failure_mode,
            "class": c.__class__.__name__,
            "enabled": c.enabled,
        }
        for c in _ALL_CONTRACTS
    ]
