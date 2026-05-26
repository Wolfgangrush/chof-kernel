"""
Ed25519-signed, hash-chained tamper-evident audit log.

Every kernel decision produces an audit entry. Entries are signed
with Ed25519 (per BMAD-PLAN.md Phase 5 cryptographic-audit-log
discipline) and chained via SHA-256 so any tampering with a prior
entry invalidates the chain.

For the C++/Rust port, this maps directly onto libsodium's
crypto_sign_ed25519 + crypto_hash_sha256 primitives.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from chof_kernel.kernel import GateDecision

GENESIS_HASH = "0" * 64
"""SHA-256 of the genesis entry."""


@dataclass(frozen=True)
class AuditEntry:
    """One immutable entry in the audit log."""

    sequence: int
    timestamp: float
    request_id: str
    gate_state: str
    h_required: float
    h_available: float
    reasoning: str
    triggered_rules: list[str]
    previous_hash: str
    """SHA-256 of the previous entry's signed body, or GENESIS_HASH for entry 0."""
    signature: str
    """Ed25519 signature of the signed-body bytes, hex-encoded."""
    signer_public_key: str
    """Ed25519 public key, raw-32-bytes hex-encoded."""

    @property
    def signed_body(self) -> bytes:
        """The canonical byte representation that is signed. Stable JSON,
        sorted keys, ASCII-encoded — same canonicalisation as the C++ port."""
        body = {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "gate_state": self.gate_state,
            "h_required": self.h_required,
            "h_available": self.h_available,
            "reasoning": self.reasoning,
            "triggered_rules": self.triggered_rules,
            "previous_hash": self.previous_hash,
        }
        return json.dumps(body, sort_keys=True, ensure_ascii=True).encode("ascii")

    def compute_hash(self) -> str:
        """SHA-256 of the signed body + signature. This is what the NEXT
        entry's previous_hash references."""
        h = hashlib.sha256()
        h.update(self.signed_body)
        h.update(self.signature.encode("ascii"))
        return h.hexdigest()


class AuditLog:
    """Tamper-evident audit log of kernel decisions.

    Each entry chains to the previous via SHA-256 of the previous entry's
    body+signature, and each entry is independently Ed25519-signed.
    """

    def __init__(self, private_key: Ed25519PrivateKey | None = None) -> None:
        self._private_key = private_key or Ed25519PrivateKey.generate()
        self._public_key: Ed25519PublicKey = self._private_key.public_key()
        self._entries: list[AuditEntry] = []

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    @property
    def public_key_hex(self) -> str:
        """Raw Ed25519 public key (32 bytes), hex-encoded."""
        raw = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return raw.hex()

    @property
    def entries(self) -> list[AuditEntry]:
        """Immutable view of the log entries."""
        return list(self._entries)

    def record(self, decision: GateDecision) -> AuditEntry:
        """Sign and append an audit entry for a kernel decision."""
        previous_hash = (
            self._entries[-1].compute_hash() if self._entries else GENESIS_HASH
        )
        sequence = len(self._entries)

        unsigned_body = {
            "sequence": sequence,
            "timestamp": decision.timestamp,
            "request_id": decision.request_id,
            "gate_state": decision.state.value,
            "h_required": decision.h_required,
            "h_available": decision.h_available,
            "reasoning": decision.reasoning,
            "triggered_rules": list(decision.triggered_rules),
            "previous_hash": previous_hash,
        }
        body_bytes = json.dumps(
            unsigned_body, sort_keys=True, ensure_ascii=True
        ).encode("ascii")
        signature = self._private_key.sign(body_bytes).hex()

        entry = AuditEntry(
            sequence=sequence,
            timestamp=decision.timestamp,
            request_id=decision.request_id,
            gate_state=decision.state.value,
            h_required=decision.h_required,
            h_available=decision.h_available,
            reasoning=decision.reasoning,
            triggered_rules=list(decision.triggered_rules),
            previous_hash=previous_hash,
            signature=signature,
            signer_public_key=self.public_key_hex,
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, str]:
        """Verify the entire chain. Returns (ok, reason).

        Checks:
          (1) every entry's signature validates against its signer_public_key
          (2) every entry's previous_hash matches the prior entry's hash
              (or GENESIS_HASH for entry 0)
          (3) every entry's signer_public_key matches this log's pubkey
        """
        expected_pk = self.public_key_hex
        for i, entry in enumerate(self._entries):
            if entry.signer_public_key != expected_pk:
                return False, (
                    f"entry {i}: signer_public_key mismatch (expected "
                    f"{expected_pk[:16]}.., got {entry.signer_public_key[:16]}..)"
                )

            expected_prev = (
                GENESIS_HASH
                if i == 0
                else self._entries[i - 1].compute_hash()
            )
            if entry.previous_hash != expected_prev:
                return False, (
                    f"entry {i}: previous_hash chain broken "
                    f"(expected {expected_prev[:16]}.., "
                    f"got {entry.previous_hash[:16]}..)"
                )

            # Verify signature
            try:
                public_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(entry.signer_public_key)
                )
                public_key.verify(
                    bytes.fromhex(entry.signature),
                    entry.signed_body,
                )
            except Exception as e:
                return False, f"entry {i}: signature verification failed ({e})"

        return True, f"all {len(self._entries)} entries verified."

    def export_json(self, path: Path | str) -> None:
        """Write the audit log to a JSON file for post-mission review."""
        path = Path(path)
        export = {
            "public_key": self.public_key_hex,
            "entry_count": len(self._entries),
            "entries": [asdict(e) for e in self._entries],
        }
        path.write_text(json.dumps(export, indent=2))

    @classmethod
    def load_for_verification(
        cls, path: Path | str
    ) -> tuple[list[AuditEntry], bool, str]:
        """Load an exported audit log file and verify the chain + sigs.

        Returns (entries, ok, reason). The class instance is not returned
        because we cannot reconstruct the private key from disk; we can
        only verify against the public key embedded in entries."""
        path = Path(path)
        data = json.loads(path.read_text())
        entries = [AuditEntry(**raw) for raw in data["entries"]]

        for i, entry in enumerate(entries):
            expected_prev = GENESIS_HASH if i == 0 else entries[i - 1].compute_hash()
            if entry.previous_hash != expected_prev:
                return (
                    entries,
                    False,
                    f"entry {i}: previous_hash chain broken at load time",
                )
            try:
                public_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(entry.signer_public_key)
                )
                public_key.verify(
                    bytes.fromhex(entry.signature),
                    entry.signed_body,
                )
            except Exception as e:
                return entries, False, f"entry {i}: signature invalid ({e})"
        return entries, True, f"loaded and verified {len(entries)} entries."
