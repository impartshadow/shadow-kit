"""Runnable Shadow Kit demo.

Run with:

    python -m shadow_kit.demo
"""

from __future__ import annotations

from shadow_kit.contracts import (
    Contract,
    ContractContext,
    Violation,
    check_all_post,
    check_all_pre,
    get_governor,
    register_contract,
)
from shadow_kit.receipts import (
    issue_contract_receipt,
    receipt_chain_proof_card,
    receipt_hash,
    receipt_proof_card,
    verify_receipt,
    verify_receipt_chain,
)


def example_verify_before_push() -> None:
    ctx = ContractContext(
        action="git_push",
        files_edited=["src/main.py"],
        response_text="Fixed the bug. Done.",
        verification_output="",
    )

    violations = check_all_pre(ctx)
    for violation in violations:
        print(f"[{violation.severity.upper()}] {violation.contract}: {violation.message}")
        print(f"  Recovery: {violation.recovery}")

    ctx.verification_output = "12 passed, 0 failed"
    violations = check_all_pre(ctx)
    print(f"After verification: {len(violations)} violations")


def example_denial_gate() -> None:
    ctx = ContractContext(
        action="respond",
        response_text=(
            "I can't access the database from here. "
            "I don't have permission to fetch those records."
        ),
        tool_calls=[],
        smoke_test_ran=False,
    )

    violations = check_all_post(ctx)
    for violation in violations:
        print(f"[{violation.severity.upper()}] {violation.contract}: {violation.message}")

    ctx.tool_calls = ["run_query"]
    violations = check_all_post(ctx)
    print(f"After trying: {len(violations)} violations")


def example_action_deferral() -> None:
    ctx = ContractContext(
        action="respond",
        response_text=(
            "Here's the approach I'd take:\n"
            "Step 1: Read the config file\n"
            "Step 2: Update the database URL\n"
            "Would you like me to go ahead with this?"
        ),
        tool_calls=[],
    )

    violations = check_all_post(ctx)
    for violation in violations:
        print(f"[{violation.severity.upper()}] {violation.contract}: {violation.message}")


class ProfanityGuard(Contract):
    """Small custom contract used to demonstrate extension."""

    name = "profanity-guard"
    failure_mode = "FM-CUSTOM-001"
    _BAD_WORDS = {"damn", "hell"}

    def check_post(self, ctx: ContractContext) -> Violation | None:
        words = set(ctx.response_text.lower().split())
        found = words & self._BAD_WORDS
        if not found:
            return None
        return Violation(
            contract=self.name,
            failure_mode=self.failure_mode,
            message=f"Response contains blocked words: {found}",
            severity="warn",
            recovery="Rephrase without profanity.",
        )


def example_custom_contract() -> None:
    register_contract(ProfanityGuard())

    ctx = ContractContext(
        action="respond",
        response_text="What the hell happened to the database?",
    )

    violations = check_all_post(ctx)
    for violation in violations:
        print(f"[{violation.severity.upper()}] {violation.contract}: {violation.message}")


def example_governance() -> None:
    governor = get_governor()
    metrics = governor.get_metrics()

    print(f"Total violations: {metrics['total_violations']}")
    print(f"Violations last hour: {metrics['violations_last_hour']}")
    print(f"Active contracts: {metrics['active_contracts']}")
    print(f"By contract: {metrics['violations_by_contract']}")

    hot = governor.get_hot_contracts(window_seconds=3600, threshold=2)
    if hot:
        print(f"Hot contracts: {hot}")


def example_signed_receipt() -> None:
    signing_key = "local-dev-key"
    ctx = ContractContext(
        action="git_push",
        files_edited=["src/main.py"],
        response_text="Done.",
    )
    violations = check_all_pre(ctx)

    receipt = issue_contract_receipt(
        agent_id="demo-agent",
        sequence=1,
        ctx=ctx,
        violations=violations,
        signing_key=signing_key,
        policy_version="demo-policy-v1",
    )

    print(f"Decision: {receipt['decision']}")
    print(f"Receipt hash: {receipt['receipt_hash']}")
    print(f"Signature valid: {verify_receipt(receipt, signing_key).valid}")
    print()
    print(receipt_proof_card(receipt, verify_receipt(receipt, signing_key)))


def example_receipt_chain() -> None:
    signing_key = "local-dev-key"
    first_ctx = ContractContext(action="respond", response_text="I read the file.")
    first_violations = check_all_post(first_ctx)
    first = issue_contract_receipt(
        agent_id="demo-agent",
        sequence=1,
        ctx=first_ctx,
        violations=first_violations,
        signing_key=signing_key,
        policy_version="demo-policy-v1",
    )

    second_ctx = ContractContext(
        action="git_push",
        files_edited=["src/main.py"],
        response_text="Done.",
    )
    second_violations = check_all_pre(second_ctx)
    second = issue_contract_receipt(
        agent_id="demo-agent",
        sequence=2,
        ctx=second_ctx,
        violations=second_violations,
        signing_key=signing_key,
        policy_version="demo-policy-v1",
        previous_hash=receipt_hash(first),
    )

    chain = [first, second]
    verification = verify_receipt_chain(chain, signing_key)
    print(receipt_chain_proof_card(chain, verification))


def main() -> None:
    sections = [
        ("Verify before push", example_verify_before_push),
        ("Denial gate", example_denial_gate),
        ("Action deferral", example_action_deferral),
        ("Custom contract", example_custom_contract),
        ("Governance metrics", example_governance),
        ("Signed receipt", example_signed_receipt),
        ("Receipt chain proof", example_receipt_chain),
    ]

    for index, (title, fn) in enumerate(sections, start=1):
        if index > 1:
            print()
        print("=" * 60)
        print(f"Example {index}: {title}")
        print("=" * 60)
        fn()


if __name__ == "__main__":
    main()
