# Skill: code-review

## Role sequence
Triage -> Execute -> Verify

## Stage: Triage
1. Identify what changed (git diff, PR description, user's summary)
2. Determine scope: single file, multi-file, architectural change
3. Check for active loops (git log -- same file touched 3+ times?)

## Stage: Execute
1. Read all changed files in full (not just the diff -- context matters)
2. Check for:
   - Logic errors and edge cases
   - Missing error handling
   - Hardcoded values that should be configurable
   - Duplication with existing code (grep for similar patterns)
   - Security issues (credentials, injection, unsafe operations)
3. Run tests if they exist
4. Be direct about problems -- no softening language

## Stage: Verify
1. Confirm tests pass after any suggested fixes
2. Check that fixes don't introduce new issues
3. Grep for duplicate patterns that need the same fix

## Contracts referenced
- `verify_before_push` -- run tests before pushing any fix
- `loop_prevention` -- re-read before editing, don't loop
- `read-before-edit` -- always read the full file first
- `completion-integrity` -- don't say "review complete" if issues remain open
