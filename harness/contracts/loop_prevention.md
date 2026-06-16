# Contract: loop-prevention

## Type
Multi-stage gate -- code-enforced via `core/contracts.py`

## Sub-contracts

### 1. Read before touching
- **Trigger:** Any file edit
- **Precondition:** The full function/file MUST be read before editing
- **Why:** Memory of code from earlier in a conversation is not reliable.

### 2. Loop tripwire (3rd commit)
- **Trigger:** 3rd+ commit touching the same function or file in a session
- **Precondition:** Full file re-read + root cause trace before any edit
- **Enforcement:** Code-enforced via `core/contracts.py:LoopTripwire`
- **Recovery:** Re-read from scratch. Trace logic. Fix and push with:
  "3rd pass -- re-read from scratch, here's what was wrong, fixed."

### 3. Conversation loop tripwire
- **Trigger:** User asks the same question or makes the same request twice
- **Precondition:** Acknowledge the miss in one sentence, then fix
- **Recovery:** "Missed it the first time -- here's what I got wrong." Then fix.

### 4. Proactive loop detection
- **Trigger:** Mid-session: same code touched twice without verification
- **Precondition:** Self-correct without being told

### 5. Dead-end protocol
- **Trigger:** Blocked on approach A
- **Precondition:** Try at least one alternative before reporting blocked
