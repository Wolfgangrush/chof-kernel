"""
Tests for the Ed25519-signed, hash-chained tamper-evident audit log.
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from chof_kernel.audit import GENESIS_HASH, AuditLog
from chof_kernel.kernel import GateDecision, GateState


def _decision(seq: int, state: GateState = GateState.GREEN) -> GateDecision:
    return GateDecision(
        request_id=f"req-{seq:03d}",
        timestamp=time.time(),
        state=state,
        h_required=70.0,
        h_available=80.0,
        reasoning=f"test decision {seq}",
        triggered_rules=[f"rule-{seq}"],
    )


def test_first_entry_points_to_genesis():
    log = AuditLog()
    entry = log.record(_decision(0))
    assert entry.sequence == 0
    assert entry.previous_hash == GENESIS_HASH


def test_subsequent_entries_chain_correctly():
    log = AuditLog()
    e0 = log.record(_decision(0))
    e1 = log.record(_decision(1))
    e2 = log.record(_decision(2))
    assert e1.previous_hash == e0.compute_hash()
    assert e2.previous_hash == e1.compute_hash()


def test_signatures_are_verifiable():
    log = AuditLog()
    for i in range(5):
        log.record(_decision(i))
    ok, reason = log.verify()
    assert ok, f"verification failed: {reason}"


def test_round_trip_export_and_load():
    log = AuditLog()
    for i in range(3):
        log.record(_decision(i, state=GateState.GREEN if i % 2 == 0 else GateState.YELLOW))

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        log.export_json(path)
        entries, ok, reason = AuditLog.load_for_verification(path)
        assert ok, reason
        assert len(entries) == 3
    finally:
        path.unlink(missing_ok=True)


def test_tampered_reasoning_invalidates_chain():
    """If an adversary modifies an entry's reasoning field after the fact,
    verification must FAIL — the signature won't validate."""
    log = AuditLog()
    for i in range(3):
        log.record(_decision(i))

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        log.export_json(path)
        # Tamper: change the reasoning of entry 1.
        data = json.loads(path.read_text())
        data["entries"][1]["reasoning"] = "MALICIOUSLY MODIFIED"
        path.write_text(json.dumps(data))

        entries, ok, reason = AuditLog.load_for_verification(path)
        assert not ok
        assert "signature" in reason.lower() or "chain" in reason.lower()
    finally:
        path.unlink(missing_ok=True)


def test_tampered_chain_link_invalidates():
    """If an adversary modifies entry 1's previous_hash to remove entry 0,
    the chain breaks and verification fails."""
    log = AuditLog()
    for i in range(3):
        log.record(_decision(i))

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        path = Path(tmp.name)
    try:
        log.export_json(path)
        data = json.loads(path.read_text())
        data["entries"][1]["previous_hash"] = GENESIS_HASH  # pretend it's the first
        path.write_text(json.dumps(data))

        entries, ok, reason = AuditLog.load_for_verification(path)
        assert not ok
    finally:
        path.unlink(missing_ok=True)


def test_public_key_is_consistent_across_entries():
    log = AuditLog()
    entries = [log.record(_decision(i)) for i in range(4)]
    pks = {e.signer_public_key for e in entries}
    assert len(pks) == 1


def test_signed_body_excludes_signature_field():
    """The signed body must NOT include the signature itself (the signature
    can't sign over itself). Verify by ensuring the canonical body is
    deterministic and excludes any signature-like keys."""
    log = AuditLog()
    entry = log.record(_decision(0))
    body = entry.signed_body
    parsed = json.loads(body.decode("ascii"))
    assert "signature" not in parsed
    assert "signer_public_key" not in parsed
