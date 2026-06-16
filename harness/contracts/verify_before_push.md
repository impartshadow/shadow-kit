# Contract: verify-before-push

## Type
Pre-push gate -- deterministic enforcement via `core/contracts.py`

## Trigger
Any response containing "Done." or "Pushed." or any `git push` command.

## Precondition
Response MUST contain a code block with verification command output matching
the fix type. Mental verification is not verification.

## Enforcement
**Code-enforced** in `core/contracts.py:VerifyBeforePush` -- blocks push if no
verification output detected in the response context.

## Verification commands by fix type

| Fix type | Verification command |
|---|---|
| Any code logic change | `python -m pytest tests/ -q` -- must show 0 failures |
| Configuration change | Run the tool/script with `--dry-run` |
| Build/deploy script | Run in test mode or dry-run |
| Data transformation | Print a sample of the output |

<!-- Customize this table for your project's specific verification commands -->

## Violation recovery
Remove "Done." claim, run the appropriate verification command, re-evaluate.
If verification fails, fix before pushing -- never push unverified logic.

## Escalation
If verification genuinely can't run locally, say so explicitly:
"Pushed -- can't verify locally; watch the next run."
