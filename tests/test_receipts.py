"""Tests for signed Shadow Kit audit receipts."""

from datetime import datetime, timezone

from shadow_kit.contracts import ContractContext, Violation
from shadow_kit.receipts import (
    ED25519,
    PROJECT_URL,
    generate_ed25519_keypair,
    issue_contract_receipt,
    issue_receipt,
    receipt_chain_proof_card,
    receipt_hash,
    receipt_proof_card,
    verify_receipt_chain,
    verify_receipt,
)


KEY = "test-signing-key"
TS = datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc)


def test_issue_receipt_verifies():
    receipt = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="send_email",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )

    result = verify_receipt(receipt, KEY)

    assert result.valid is True
    assert result.errors == []
    assert result.receipt_hash == receipt["receipt_hash"]


def test_verify_receipt_detects_tampering():
    receipt = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="send_email",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    tampered = {**receipt, "decision": "block"}

    result = verify_receipt(tampered, KEY)

    assert result.valid is False
    assert "signature mismatch" in result.errors
    assert "receipt_hash mismatch" in result.errors


def test_ed25519_receipt_verifies_without_private_key():
    private_key, public_key = generate_ed25519_keypair()
    receipt = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="send_email",
        decision="allow",
        signing_key=private_key,
        signature_algorithm=ED25519,
        verification_key=public_key,
        timestamp=TS,
        receipt_id="r-public-1",
    )

    result = verify_receipt(receipt)

    assert result.valid is True
    assert receipt["verification_key"] == public_key
    assert private_key not in receipt.values()


def test_ed25519_receipt_rejects_tampering():
    private_key, _ = generate_ed25519_keypair()
    receipt = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="send_email",
        decision="allow",
        signing_key=private_key,
        signature_algorithm=ED25519,
        timestamp=TS,
        receipt_id="r-public-2",
    )
    receipt["decision"] = "block"

    result = verify_receipt(receipt)

    assert result.valid is False
    assert "signature mismatch" in result.errors


def test_receipt_chain_previous_hash_verifies():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    second = issue_receipt(
        agent_id="agent-a",
        sequence=2,
        action="git_push",
        decision="block",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        timestamp=TS,
        receipt_id="r-2",
    )

    result = verify_receipt(second, KEY, expected_previous_hash=receipt_hash(first))
    broken = verify_receipt(second, KEY, expected_previous_hash="wrong")

    assert result.valid is True
    assert broken.valid is False
    assert "previous_hash mismatch" in broken.errors


def test_issue_contract_receipt_derives_decision_and_metering():
    ctx = ContractContext(
        action="git_push",
        files_edited=["src/main.py"],
        tool_calls=["Bash"],
    )
    violations = [
        Violation(
            contract="verify-before-push",
            failure_mode="FM-002",
            message="No verification output.",
            severity="block",
            recovery="Run tests.",
        )
    ]

    receipt = issue_contract_receipt(
        agent_id="agent-a",
        sequence=3,
        ctx=ctx,
        violations=violations,
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-3",
    )

    assert receipt["decision"] == "block"
    assert receipt["metering"] == {
        "tool_calls": 1,
        "files_edited": 1,
        "violations": 1,
    }
    assert receipt["violations"][0]["contract"] == "verify-before-push"
    assert verify_receipt(receipt, KEY).valid is True


def test_verify_receipt_chain_accepts_ordered_chain():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    second = issue_receipt(
        agent_id="agent-a",
        sequence=2,
        action="git_push",
        decision="block",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        timestamp=TS,
        receipt_id="r-2",
    )

    result = verify_receipt_chain([first, second], KEY, expected_agent_id="agent-a")

    assert result.valid is True
    assert result.errors == []
    assert result.receipt_hashes == [receipt_hash(first), receipt_hash(second)]
    assert result.first_sequence == 1
    assert result.last_sequence == 2


def test_verify_receipt_chain_detects_missing_middle_receipt():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    third = issue_receipt(
        agent_id="agent-a",
        sequence=3,
        action="send_email",
        decision="allow",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        timestamp=TS,
        receipt_id="r-3",
    )

    result = verify_receipt_chain([first, third], KEY)

    assert result.valid is False
    assert "receipt[1]: non-contiguous sequence" in result.errors


def test_verify_receipt_chain_detects_reordered_or_unlinked_receipts():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    second = issue_receipt(
        agent_id="agent-a",
        sequence=2,
        action="git_push",
        decision="block",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        timestamp=TS,
        receipt_id="r-2",
    )

    result = verify_receipt_chain([second, first], KEY)

    assert result.valid is False
    assert "receipt[0]: previous_hash mismatch" in result.errors
    assert "receipt[1]: previous_hash mismatch" in result.errors


def test_verify_receipt_chain_detects_mixed_agents():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    second = issue_receipt(
        agent_id="agent-b",
        sequence=2,
        action="respond",
        decision="allow",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        timestamp=TS,
        receipt_id="r-2",
    )

    result = verify_receipt_chain([first, second], KEY)

    assert result.valid is False
    assert "receipt[1]: mixed agent_id" in result.errors


def test_receipt_proof_card_has_public_audit_fields():
    receipt = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        policy_version="policy-a",
        metering={"tool_calls": 2},
        timestamp=TS,
        receipt_id="r-1",
    )
    verification = verify_receipt(receipt, KEY)

    card = receipt_proof_card(receipt, verification)

    assert "### Governed Agent Receipt" in card
    assert "- Agent: `agent-a`" in card
    assert "- Decision: `allow`" in card
    assert "- Policy: `policy-a`" in card
    assert "- Verification: `valid`" in card
    assert "- Metering: `tool_calls=2`" in card
    assert KEY not in card
    assert PROJECT_URL in card
    assert "pip install shadow-kit" in card


def test_receipt_chain_proof_card_summarizes_latest_hash():
    first = issue_receipt(
        agent_id="agent-a",
        sequence=1,
        action="respond",
        decision="allow",
        signing_key=KEY,
        timestamp=TS,
        receipt_id="r-1",
    )
    second = issue_receipt(
        agent_id="agent-a",
        sequence=2,
        action="send_email",
        decision="warn",
        signing_key=KEY,
        previous_hash=receipt_hash(first),
        policy_version="policy-b",
        timestamp=TS,
        receipt_id="r-2",
    )
    verification = verify_receipt_chain([first, second], KEY)

    card = receipt_chain_proof_card([first, second], verification)

    assert "### Governed Agent Receipt Chain" in card
    assert "- Receipts: `2`" in card
    assert "- Sequence range: `1` to `2`" in card
    assert "- Latest decision: `warn`" in card
    assert f"- Latest hash: `{receipt_hash(second)}`" in card
    assert "- Verification: `valid`" in card
    assert KEY not in card
    assert PROJECT_URL in card
    assert "pip install shadow-kit" in card
