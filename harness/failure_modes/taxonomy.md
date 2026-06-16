# Failure Mode Taxonomy

Named failure modes with automated recovery paths. Each mode maps to a
contract that should catch it and a code-level guard where possible.

---

## FM-001: capability-denial
**Pattern:** Agent says "I can't access X" without trying.
**Root cause:** Default to caution over action. LLM tendency to hedge.
**Contract:** `pre_denial_gate`
**Code guard:** `core/contracts.py:PreDenialGate` -- scans response for denial phrases.
**Recovery:** Block the denial. Run the smoke test. Show the output. Then decide.

## FM-002: unverified-push
**Pattern:** "Done." without running verification command.
**Root cause:** Mental verification feels like real verification. It isn't.
**Contract:** `verify_before_push`
**Code guard:** `core/contracts.py:VerifyBeforePush` -- blocks push without output.
**Recovery:** Run verification. Paste output. Then push.

## FM-003: edit-loop
**Pattern:** 3+ commits to the same file without fixing the root cause.
**Root cause:** Fixing symptoms instead of reading the full context.
**Contract:** `loop_prevention`
**Code guard:** `core/contracts.py:LoopTripwire` -- graduated escalation.
**Recovery:** Re-read entire file. Trace logic. One fix, verified.

## FM-006: misunderstood-intent
**Pattern:** Agent answers a different question than was asked.
**Root cause:** Over-indexing on what the agent was already doing vs. what was asked.
**Contract:** Harness-side -- read the thread.
**Code guard:** None. This requires semantic understanding.
**Recovery:** Re-read the exact words. Answer THAT question. Don't redirect.

## FM-007: lost-context
**Pattern:** Agent forgets something decided earlier in the session.
**Root cause:** Context window pressure, compaction, or not persisting decisions.
**Contract:** `loop_prevention` (conversation loop tripwire)
**Code guard:** Decision log tools exist but aren't always called.
**Recovery:** Check decision log. Update session handoff after every push.

## FM-008: premature-proposal
**Pattern:** Proposing an approach instead of executing it.
**Root cause:** Risk aversion. Defaulting to "shall I?" instead of doing.
**Contract:** Runtime skill (default to action).
**Code guard:** None -- semantic.
**Recovery:** Just do it. Report what you did, not what you plan to do.

## FM-010: sycophantic-validation
**Pattern:** Praising the user's approach instead of evaluating it honestly.
**Root cause:** RLHF optimization for user satisfaction over truth.
**Contract:** None -- meta-pattern.
**Code guard:** None possible. Requires ongoing vigilance.
**Recovery:** Evaluate against outcomes. Push back with one clear objection
when the user is going down a bad path.

## FM-011: explain-instead-of-act
**Pattern:** Agent proposes/architects/gives-manual-instructions instead of executing.
**Sub-patterns:**
- (a) deferred-action -- "would you like me to", "I can set up", "here's the approach"
- (b) manual-instruction -- "go to settings", "click on X", "navigate to"
**Root cause:** Risk aversion. LLM tendency to describe rather than do.
**Contract:** `action-deferral-guard`
**Code guard:** `core/contracts.py:ActionDeferralGuard`
**Recovery:** Execute directly. Report what you did, not what you plan to do.

## FM-013: topic-overrun
**Pattern:** Agent continues a topic after user signals closure.
**Root cause:** Trying to be thorough when the user wants to move on.
**Contract:** `topic-overrun-guard`
**Code guard:** `core/contracts.py:TopicOverrunGuard`
**Recovery:** Drop the thread. If something is genuinely urgent, save it for later.

## FM-014: completion-integrity
**Pattern:** Agent claims "done" while acknowledging unresolved gaps.
**Root cause:** Commit code, lead with "shipped", then list gaps.
**Contract:** `completion-integrity`
**Code guard:** `core/contracts.py:CompletionIntegrity`
**Recovery:** Remove the completion claim. Lead with what's done, list what's remaining.

## FM-015: unsafe-git-operations
**Pattern:** Force-push to protected branches, push to wrong remotes.
**Root cause:** Executing destructive git operations without parameter validation.
**Contract:** `git-push-target-guard`
**Code guard:** `core/contracts.py:GitPushTargetGuard`
**Recovery:** Push to a feature branch instead, or remove --force.

## FM-017: sensitive-path-write
**Pattern:** Writing to .env, credential files, SSH keys, /etc/.
**Root cause:** Agent doesn't distinguish sensitive paths from normal files.
**Contract:** `dangerous-path-guard`
**Code guard:** `core/contracts.py:DangerousPathGuard`
**Recovery:** Use a secrets manager for credentials. Don't write to sensitive paths.

---

## Adding new failure modes

When you observe a new failure pattern:

1. **Name it** -- assign FM-XXX code and a descriptive name
2. **Document the pattern** -- what the agent does wrong
3. **Identify the root cause** -- why the LLM does this
4. **Create a contract** -- write a Contract subclass to catch it
5. **Test it** -- verify the contract catches the failure without false positives
6. **Ship it** -- register the contract and update this taxonomy

Code enforcement is the default. Prose rules are a last resort.
