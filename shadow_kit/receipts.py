"""Signed audit receipts for governed agent actions.

Receipts are the portable evidence layer for Shadow Kit. Contract checks decide
whether an action should pass, warn, or block; receipts make that decision
auditable after the fact.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from shadow_kit.contracts import ContractContext, Violation

SCHEMA_VERSION = "shadow-kit.receipt.v1"

PROJECT_URL = "https://github.com/impartshadow/shadow-kit"

# Every proof card carries a verifiable attribution footer. The card is the
# portable artifact users paste into READMEs, demos, audit exports, and posts,
# so the footer turns each shared receipt into a self-serve verification path
# back to the kit: usage becomes distribution at zero marginal cost.
PROOF_CARD_FOOTER = (
    f"_Receipt schema `{SCHEMA_VERSION}`. "
    f"Verify this receipt yourself: `pip install shadow-kit` → {PROJECT_URL}_"
)


@dataclass(frozen=True)
class ReceiptVerification:
    """Result of verifying a signed receipt."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    receipt_hash: str = ""


@dataclass(frozen=True)
class ReceiptChainVerification:
    """Result of verifying an ordered receipt chain."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    receipt_hashes: list[str] = field(default_factory=list)
    agent_id: str = ""
    first_sequence: int | None = None
    last_sequence: int | None = None


def canonical_json(data: dict[str, Any]) -> str:
    """Return deterministic JSON for signing and hashing."""

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(data: dict[str, Any]) -> str:
    """Return a stable SHA-256 hash of a JSON-like mapping."""

    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def _key_bytes(signing_key: str | bytes) -> bytes:
    if isinstance(signing_key, bytes):
        return signing_key
    return signing_key.encode("utf-8")


def _unsigned(receipt: dict[str, Any]) -> dict[str, Any]:
    data = dict(receipt)
    data.pop("signature", None)
    data.pop("receipt_hash", None)
    return data


def sign_payload(payload: dict[str, Any], signing_key: str | bytes) -> str:
    """Sign a receipt payload with HMAC-SHA256."""

    return hmac.new(
        _key_bytes(signing_key),
        canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def receipt_hash(receipt: dict[str, Any]) -> str:
    """Hash the signed receipt envelope."""

    data = dict(receipt)
    data.pop("receipt_hash", None)
    return canonical_hash(data)


def issue_receipt(
    *,
    agent_id: str,
    sequence: int,
    action: str,
    decision: str,
    signing_key: str | bytes,
    policy_version: str = "local",
    context_hash: str = "",
    violations: list[Violation] | None = None,
    metering: dict[str, Any] | None = None,
    previous_hash: str = "",
    timestamp: datetime | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    """Create a signed audit receipt for one governed action.

    The signature covers the receipt payload except the signature and
    receipt_hash fields. The receipt_hash covers the signed envelope and is the
    value to store as the next receipt's previous_hash.
    """

    ts = timestamp or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    violation_records = [
        {
            "contract": v.contract,
            "failure_mode": v.failure_mode,
            "severity": v.severity,
            "message": v.message,
            "recovery": v.recovery,
        }
        for v in (violations or [])
    ]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "receipt_id": receipt_id or str(uuid4()),
        "agent_id": agent_id,
        "sequence": sequence,
        "timestamp": ts.isoformat(),
        "action": action,
        "decision": decision,
        "policy_version": policy_version,
        "context_hash": context_hash,
        "violations": violation_records,
        "metering": metering or {},
        "previous_hash": previous_hash,
    }
    signature = sign_payload(payload, signing_key)
    signed = {**payload, "signature": signature}
    return {**signed, "receipt_hash": receipt_hash(signed)}


def issue_contract_receipt(
    *,
    agent_id: str,
    sequence: int,
    ctx: ContractContext,
    violations: list[Violation],
    signing_key: str | bytes,
    policy_version: str = "local",
    previous_hash: str = "",
    timestamp: datetime | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any]:
    """Create a receipt directly from a contract-check result."""

    decision = "allow"
    if any(v.severity == "block" for v in violations):
        decision = "block"
    elif violations:
        decision = "warn"

    context = {
        "action": ctx.action,
        "action_params": ctx.action_params,
        "files_edited": ctx.files_edited,
        "tool_calls": ctx.tool_calls,
    }

    return issue_receipt(
        agent_id=agent_id,
        sequence=sequence,
        action=ctx.action,
        decision=decision,
        signing_key=signing_key,
        policy_version=policy_version,
        context_hash=canonical_hash(context),
        violations=violations,
        metering={
            "tool_calls": len(ctx.tool_calls),
            "files_edited": len(ctx.files_edited),
            "violations": len(violations),
        },
        previous_hash=previous_hash,
        timestamp=timestamp,
        receipt_id=receipt_id,
    )


def verify_receipt(
    receipt: dict[str, Any],
    signing_key: str | bytes,
    *,
    expected_previous_hash: str | None = None,
) -> ReceiptVerification:
    """Verify a receipt signature, envelope hash, and optional chain link."""

    errors: list[str] = []

    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")

    signature = receipt.get("signature")
    if not isinstance(signature, str) or not signature:
        errors.append("missing signature")
    else:
        expected = sign_payload(_unsigned(receipt), signing_key)
        if not hmac.compare_digest(signature, expected):
            errors.append("signature mismatch")

    computed_hash = receipt_hash(receipt)
    stored_hash = receipt.get("receipt_hash")
    if stored_hash and stored_hash != computed_hash:
        errors.append("receipt_hash mismatch")

    if expected_previous_hash is not None:
        previous_hash = receipt.get("previous_hash", "")
        if previous_hash != expected_previous_hash:
            errors.append("previous_hash mismatch")

    return ReceiptVerification(
        valid=not errors,
        errors=errors,
        receipt_hash=computed_hash,
    )


def verify_receipt_chain(
    receipts: list[dict[str, Any]],
    signing_key: str | bytes,
    *,
    expected_agent_id: str | None = None,
    require_contiguous_sequence: bool = True,
) -> ReceiptChainVerification:
    """Verify signatures, hashes, links, and optional sequence continuity.

    Receipts must be ordered from oldest to newest. This creates the portable
    proof boundary used by demos and gateway exports: anyone with the public
    bundle and verification key can detect tampering, deletion, or reordering.
    """

    if not receipts:
        return ReceiptChainVerification(valid=False, errors=["empty receipt chain"])

    errors: list[str] = []
    hashes: list[str] = []
    first_agent_id = str(receipts[0].get("agent_id", ""))
    first_sequence = _sequence(receipts[0])
    previous_hash = ""
    previous_sequence: int | None = None

    for index, receipt in enumerate(receipts):
        prefix = f"receipt[{index}]"
        result = verify_receipt(
            receipt,
            signing_key,
            expected_previous_hash=previous_hash,
        )
        hashes.append(result.receipt_hash)
        errors.extend(f"{prefix}: {error}" for error in result.errors)

        agent_id = receipt.get("agent_id")
        if not isinstance(agent_id, str) or not agent_id:
            errors.append(f"{prefix}: missing agent_id")
        elif expected_agent_id is not None and agent_id != expected_agent_id:
            errors.append(f"{prefix}: agent_id mismatch")
        elif agent_id != first_agent_id:
            errors.append(f"{prefix}: mixed agent_id")

        sequence = _sequence(receipt)
        if sequence is None:
            errors.append(f"{prefix}: invalid sequence")
        elif (
            require_contiguous_sequence
            and previous_sequence is not None
            and sequence != previous_sequence + 1
        ):
            errors.append(f"{prefix}: non-contiguous sequence")

        previous_hash = result.receipt_hash
        previous_sequence = sequence

    return ReceiptChainVerification(
        valid=not errors,
        errors=errors,
        receipt_hashes=hashes,
        agent_id=first_agent_id,
        first_sequence=first_sequence,
        last_sequence=previous_sequence,
    )


def receipt_proof_card(
    receipt: dict[str, Any],
    verification: ReceiptVerification | None = None,
) -> str:
    """Render a public Markdown proof card for a single receipt.

    The card intentionally excludes the signing key and full action context.
    It is safe to paste into demos, READMEs, customer updates, or audit exports.
    """

    if verification is None:
        status = "unverified"
        errors = ""
    else:
        status = "valid" if verification.valid else "invalid"
        errors = ", ".join(verification.errors)

    violations = receipt.get("violations", [])
    contract_names = [
        str(item.get("contract", "unknown"))
        for item in violations
        if isinstance(item, dict)
    ]
    if not contract_names:
        contract_text = "none"
    else:
        contract_text = ", ".join(contract_names)

    metering = receipt.get("metering", {})
    if isinstance(metering, dict) and metering:
        metering_text = ", ".join(
            f"{key}={metering[key]}" for key in sorted(metering)
        )
    else:
        metering_text = "none"

    lines = [
        "### Governed Agent Receipt",
        "",
        f"- Agent: `{receipt.get('agent_id', '')}`",
        f"- Sequence: `{receipt.get('sequence', '')}`",
        f"- Action: `{receipt.get('action', '')}`",
        f"- Decision: `{receipt.get('decision', '')}`",
        f"- Policy: `{receipt.get('policy_version', '')}`",
        f"- Receipt hash: `{receipt.get('receipt_hash', '')}`",
        f"- Previous hash: `{receipt.get('previous_hash', '')}`",
        f"- Verification: `{status}`",
        f"- Contracts: `{contract_text}`",
        f"- Metering: `{metering_text}`",
    ]
    if errors:
        lines.append(f"- Verification errors: `{errors}`")
    lines.extend(["", PROOF_CARD_FOOTER])
    return "\n".join(lines)


def receipt_chain_proof_card(
    receipts: list[dict[str, Any]],
    verification: ReceiptChainVerification,
) -> str:
    """Render a concise public Markdown proof card for a receipt chain."""

    latest = receipts[-1] if receipts else {}
    status = "valid" if verification.valid else "invalid"
    lines = [
        "### Governed Agent Receipt Chain",
        "",
        f"- Agent: `{verification.agent_id}`",
        f"- Receipts: `{len(receipts)}`",
        f"- Sequence range: `{verification.first_sequence}` to `{verification.last_sequence}`",
        f"- Latest decision: `{latest.get('decision', '')}`",
        f"- Latest policy: `{latest.get('policy_version', '')}`",
        f"- Latest hash: `{verification.receipt_hashes[-1] if verification.receipt_hashes else ''}`",
        f"- Verification: `{status}`",
    ]
    if verification.errors:
        lines.append(f"- Verification errors: `{', '.join(verification.errors)}`")
    lines.extend(["", PROOF_CARD_FOOTER])
    return "\n".join(lines)


def _sequence(receipt: dict[str, Any]) -> int | None:
    sequence = receipt.get("sequence")
    if isinstance(sequence, int):
        return sequence
    return None
