# AI Agents Do Not Need Better Prompts. They Need Runtime Contracts.

Most agent failures are not mysteries. They are repeated boundary failures:

- The agent says it cannot do something before trying.
- The agent claims a task is complete before verification.
- The agent proposes a plan when it already has authority to execute.
- The agent writes code without first reading the file it is changing.
- The agent sends output to the wrong surface because the policy lived only in prose.
- The agent forgets a correction after compaction and repeats the same failure.

The common diagnosis is "make the prompt clearer." That works until the next
long session, model swap, compaction, tool error, or high-pressure task.

Prompts are a weak place to store operational guarantees. They are advisory,
context-dependent, and interpreted by the same system that is failing.

Runtime contracts are different. A contract turns a recurring failure into a
deterministic precondition or postcondition:

```text
action/response -> contract check -> allow, warn, or block -> signed receipt
```

That is the boundary agents need.

## The failure pattern

Agent products usually start with trust language:

- "The agent will verify before pushing."
- "The agent will never send email without approval."
- "The agent will browse before saying it does not know."
- "The agent will not expose secrets."
- "The agent will follow the user's correction next time."

Those are not guarantees. They are wishes unless something outside the model
checks them.

The failure is especially dangerous because the agent often sounds competent
while violating the rule. It writes a clean summary, says "done," and only later
does the user discover that tests never ran, the file was not written, the wrong
account was used, or the action was never attempted.

The useful unit is not "prompt instruction." The useful unit is:

- **Failure mode:** the repeated bad behavior
- **Trigger:** when the behavior is possible
- **Contract:** the deterministic check
- **Recovery:** what must happen before the action can continue
- **Receipt:** evidence of what was allowed or blocked

## The first contracts every agent should have

| Contract | Blocks | Why it matters |
|---|---|---|
| `pre-denial-gate` | Saying "I can't" before trying a tool | Prevents false capability denials |
| `verify-before-push` | Code push without verification output | Prevents fake completion |
| `read-before-edit` | Editing a file without reading it first | Prevents blind patches |
| `action-deferral-guard` | Asking permission for authorized low-risk work | Keeps agents operational |
| `completion-integrity` | Saying "done" while listing unresolved gaps | Prevents misleading status |
| `dangerous-path-guard` | Writes to credentials, secrets, or system paths | Prevents high-blast-radius mistakes |

These are not theoretical. They came from repeated failures in a live agent
runtime and were converted into code.

## What a contract looks like

The agent prepares an action context:

```python
from shadow_kit.contracts import ContractContext, check_all_pre

ctx = ContractContext(
    action="git_push",
    files_edited=["src/main.py"],
    response_text="Fixed it. Done.",
    verification_output="",
)

violations = check_all_pre(ctx)
for violation in violations:
    print(violation.severity, violation.contract, violation.recovery)
```

`verify-before-push` blocks because the action has no verification output. The
agent does not get to "remember" the rule. The runtime enforces it.

## Why receipts matter

Contracts answer "should this pass?" Receipts answer "what actually happened?"

A signed receipt records:

- governed agent id
- action
- allow/warn/block decision
- policy version
- violations
- metering fields
- previous receipt hash
- HMAC signature
- receipt hash

That creates an audit trail that can survive beyond the model's context window.

```python
from shadow_kit.receipts import issue_contract_receipt, verify_receipt

receipt = issue_contract_receipt(
    agent_id="demo-agent",
    sequence=1,
    ctx=ctx,
    violations=violations,
    signing_key="local-dev-key",
    policy_version="runtime-contracts-v1",
)

assert verify_receipt(receipt, "local-dev-key").valid
print(receipt["decision"], receipt["receipt_hash"])
```

In the open-source kit, the local process provides the signing key. In a
commercial gateway, the signing key lives outside the agent container, so the
agent cannot forge its own allow receipts.

## What this changes

Without contracts, agent governance is mostly trust:

```text
user instruction -> model interpretation -> action -> narrative summary
```

With contracts, the boundary is explicit:

```text
user instruction -> model intent -> runtime contract -> allowed action -> signed receipt
```

That gives teams a way to inspect agent behavior without reading transcripts
line by line. The important question becomes: which actions were allowed,
blocked, retried, or recovered?

## Try it

```bash
git clone https://github.com/impartshadow/shadow.git
cd shadow/shadow-kit
pip install -e .
python3 examples/basic_assistant.py
pytest -q
```

Start with one contract. Pick a failure your agent has repeated twice. Name it,
write the check, and make the runtime block it before it reaches a user or an
external system.

That is the core move: stop treating repeated agent failures as prompt bugs.
Treat them as product requirements.
