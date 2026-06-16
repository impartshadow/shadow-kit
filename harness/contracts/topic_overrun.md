# Contract: topic-overrun-guard

## Type
Post-response gate -- deterministic enforcement via `core/contracts.py`

## Trigger
Any response where the agent acknowledges the user's closure signal
(done, fine, good, set) and then continues with the same topic.

## Precondition
When the user signals closure, the agent MUST stop that thread.

## What this catches
- "Got it, but also..." after user says "that's fine"
- "One more thing..." after user says "done"
- "Since you mentioned..." to extend a closed topic
- "While we're at it..." to piggyback on closure

## Enforcement
**Code-enforced** in `core/contracts.py:TopicOverrunGuard` -- regex scan
on response text for overrun patterns.

## Violation recovery
Drop the current thread. If there's genuinely urgent follow-up, save it
for later -- don't append it to a closure response.

## Escalation
None. This is always a soft correction.
