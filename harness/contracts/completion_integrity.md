# Contract: completion-integrity

## Type
Post-response gate -- deterministic enforcement via `core/contracts.py`

## Trigger
Any response containing strong completion claims ("done", "shipped",
"all deployed", "everything is wired") alongside gap acknowledgments
("not done", "still missing", "not yet implemented").

## Precondition
If you claim something is done, it must actually be done. The response
must not simultaneously acknowledge unresolved gaps.

## What this catches
- "Shipped and wired" followed by "not yet implemented" items
- "All three are done" with a "what's NOT done" section
- "Complete." with "partially" or "half-done" in the same response

## Enforcement
**Code-enforced** in `core/contracts.py:CompletionIntegrity` -- detects
strong completion claims co-occurring with 2+ gap acknowledgments.
Exempt for audit/review responses that intentionally contrast claims
vs. reality.

## Violation recovery
Remove the completion claim. Lead with what's actually done, then list
what's remaining. Don't signal done until it's done.
