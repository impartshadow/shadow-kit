# Contract: pre-denial-gate

## Type
Pre-response gate -- deterministic enforcement via `core/contracts.py`

## Trigger
Any response containing denial phrases: "can't access", "don't have access",
"unavailable", "not possible", "I can't".

## Precondition
Before ANY denial response, ALL of the following must be true:
1. Checked your capability inventory
2. Tried every listed path for that resource
3. Ran a smoke test -- actually executed a command to confirm access is broken

## Enforcement
**Code-enforced** in `core/contracts.py:PreDenialGate` -- scans outgoing
responses for denial phrases and flags violations when no smoke test output
is present in the conversation context.

## Known paths to document

<!-- Fill this in with your agent's capabilities. Example:
| "I can't..." | Actually can -- try this |
|---|---|
| Access Gmail | `python3 -c "from scripts.gmail_utils import get_service; ..."` |
| Browse a webpage | `your_browse_tool` with the URL |
| Search the web | `your_search_tool` with the query |
-->

## Violation recovery
Block the denial. Run the smoke test. Show the output. Then decide.

## Escalation
If all listed paths genuinely fail, include the error output and say:
"All paths failed -- here's what I tried: [output]"
