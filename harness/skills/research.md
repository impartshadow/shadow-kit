# Skill: research

## Role sequence
Triage -> Execute -> Verify

## Stage: Triage
1. Identify the source (URL, topic, named content)
2. If named content (episode, article), search for it -- don't ask the user for the URL
3. Route to appropriate tool for fetching

## Stage: Execute
1. Fetch content via your agent's web tools
2. Follow sources and verify claims -- not just a summary
3. Structure output: bottom line first, key points, evidence, actionable takeaways
4. Show investigation path: inline narration OR "Path taken:" header

## Stage: Verify
1. Cross-check search results before presenting -- no conflicting or stale data
2. If claims conflict, note the discrepancy explicitly
3. Flag uncertainty rather than guessing

## Contracts referenced
- `pre_denial_gate` -- before claiming a resource is inaccessible, try all paths
- Tool routing -- use your configured tools, not built-in alternatives

## Output format
- Newsletter/article: full research-style analysis (follow sources, verify)
- Quick lookup: direct answer, cited
- Comparison: structured table
