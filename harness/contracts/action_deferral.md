# Contract: action-deferral-guard

## Type
Post-response gate -- deterministic enforcement via `core/contracts.py`

## Trigger
Any response containing 2+ proposal/instruction markers without evidence
of actual tool execution in the same turn.

## Sub-patterns

### (a) Deferred action
- "Would you like me to..."
- "I can set up / configure / create..."
- "Here's the approach..."
- "Steps: 1. ..."

### (b) Manual instruction
- "Go to settings..."
- "Click on 'X'..."
- "Navigate to..."
- "You'll need to..."

## Precondition
The agent must attempt execution via tools before falling back to
proposals or instructions.

## Exemptions
- Discussion/brainstorm mode (user explicitly said "just brainstorming")
- Hypothetical questions ("how would you..." / "what if...")
- Execution tool was called this turn
- Past-tense completion markers present ("Done.", "Pushed.", "Created.")
- Blocker evidence ("blocked by", "error:", "failed:")

## Enforcement
**Code-enforced** in `core/contracts.py:ActionDeferralGuard` -- classifies
tool calls as execution vs. reconnaissance. Fires when 2+ proposal/instruction
markers appear without execution evidence.

## Violation recovery
Execute the action directly. If a tool exists for it, call the tool.
Only explain/propose if execution genuinely failed -- and show the error output.
