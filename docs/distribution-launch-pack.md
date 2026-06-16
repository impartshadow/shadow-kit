# Shadow Kit Distribution Launch Pack

## Positioning

Shadow Kit is for agent builders who are tired of prompts being treated as
policy. It turns recurring agent failures into runtime contracts that block bad
actions before they reach users, repos, or external systems.

Primary claim:

> Better prompts do not make agents trustworthy. Runtime contracts do.

Concrete failure examples:

- "I can't access that" without trying a tool first
- "Done" after code changes with no verification
- "Want me to fix that?" when the agent already has authority
- manual instructions when an API or shell path exists
- pushes to protected branches without a verification receipt

## Audience

Start with builders who already feel the pain:

- Claude Code / Codex power users
- founders building internal AI operators
- platform engineers wrapping LLM agents around production tools
- AI safety people who care about enforcement more than eval theater
- technical operators who have seen agents fabricate completion

Avoid broad "AI productivity" audiences. They will like the idea and do
nothing with it.

## Core CTA

```bash
pip install git+https://github.com/impartshadow/shadow.git
python -m shadow_kit.demo
```

Repo:

https://github.com/impartshadow/shadow

Ask:

> Try the demo. If you have a recurring agent failure, send the transcript. I
> will turn the failure into a contract.

## Launch Post

Title:

AI agents do not need better prompts. They need runtime contracts.

Body:

Most AI agent failures are not random.

They are repeatable product defects:

- claiming a task is done without verification
- saying "I can't access that" before trying the available tool
- asking "want me to fix it?" when the agent already has authority
- giving manual instructions instead of using the API
- pushing code with no receipt trail

Shadow Kit treats those failures as runtime policy violations, not vibes.

The pattern is simple:

1. name the failure mode
2. write a deterministic contract
3. check the action before it reaches the outside world
4. emit a signed receipt showing what was allowed or blocked

This is the same enforcement layer Shadow uses on itself.

Run the demo:

```bash
pip install git+https://github.com/impartshadow/shadow.git
python -m shadow_kit.demo
```

If your agent has a recurring failure mode, send me the transcript. I will turn
it into a contract.

https://github.com/impartshadow/shadow

## Short Posts

### 1. Prompt Fatigue

People keep trying to fix agent reliability with longer prompts.

That is backwards.

If the failure is recurring, it should not live in the prompt. It should become
a runtime contract.

Shadow Kit demo:
https://github.com/impartshadow/shadow

### 2. Completion Claims

The most expensive agent failure is not a syntax error.

It is the agent saying "done" when nothing was verified.

Shadow Kit blocks that class directly: no verification, no completion claim.

Demo:
https://github.com/impartshadow/shadow

### 3. Capability Denial

Agents often say "I can't access that" while sitting on a shell, browser,
filesystem, or API token.

That should be a contract violation.

Attempt first. Deny only after evidence.

Shadow Kit:
https://github.com/impartshadow/shadow

### 4. Authority Deferral

"Want me to fix it?" is often a bug.

If the agent has standing authority, deferral is not politeness. It is a failed
execution path.

Shadow Kit turns that into an enforceable contract.

https://github.com/impartshadow/shadow

### 5. Receipts

Agent governance needs receipts, not trust-me summaries.

Every governed Shadow Kit decision can emit a signed receipt:

- allowed or blocked
- contract fired
- recovery path
- policy version
- receipt hash

Demo:
https://github.com/impartshadow/shadow

## Reply Targets

Use this only where the topic is already live:

- "my coding agent lied about pushing"
- "Claude Code said it completed X but did not"
- "agent governance"
- "AI agent evals are not enough"
- "how do I make agents reliable in production"
- "agents need permissions / policy / control plane"

Reply pattern:

> This is the exact failure class Shadow Kit is built around: recurring agent
> failures should become runtime contracts, not longer prompts. The demo blocks
> unverified completion, capability denial, and authority deferral:
> https://github.com/impartshadow/shadow

## Daily Loop

Until there is inbound:

1. post one short failure-mode claim
2. reply to 3 relevant agent-builder threads
3. log which hook got engagement
4. convert any concrete failure transcript into a new contract or example

Do not build more features until at least three external builders have tried the
demo or provided failure transcripts.
