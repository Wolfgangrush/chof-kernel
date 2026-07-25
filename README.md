<div align="center">
  <img src="docs/banner.png" width="820"/>
  <p><strong>Embedded human-oversight kernel for autonomous systems</strong></p>
  <p>Visit the live site: <a href="https://wolfgangrush.github.io">wolfgangrush.github.io</a></p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"/>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs welcome"/>
</p>


<div align="center">
  <img src="docs/banner.png" width="820"/>
  <p><strong>Embedded human-oversight kernel for autonomous systems</strong></p>
  <p>Visit the live site: <a href="https://wolfgangrush.github.io">wolfgangrush.github.io</a></p>
</div>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"/>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs welcome"/>
</p>


# chof-kernel

> **Embedded human-oversight kernel for autonomous systems.**
> The Tier-2 companion to [`chof-calc`](https://github.com/Wolfgangrush/chof-calc).
> Python reference implementation of the CHOF-Kernel tactical safety governor.
> Production target: C++/Rust port for ROS2 / PX4 / ArduPilot integration.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/Status-0.1.0--alpha-orange)](pyproject.toml)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](pyproject.toml)
[![Tests: 27 passing](https://img.shields.io/badge/Tests-27_passing-brightgreen)](tests/)
[![Crypto: Ed25519 + SHA-256](https://img.shields.io/badge/Crypto-Ed25519_+_SHA--256-purple)](src/chof_kernel/audit.py)

---

## TL;DR

`chof-kernel` is a **tactical safety governor** that sits inside an autonomous
system's flight stack, between the perception/classifier output and the
engagement-decision module. On each proposed engagement, it computes whether
the available human oversight meets the required oversight envelope, and
emits a four-state gate decision (GREEN / YELLOW / RED / BLACK) plus an
Ed25519-signed tamper-evident audit log entry.

This is the **runtime** counterpart to the policy-time
[`chof-calc`](https://github.com/Wolfgangrush/chof-calc) assessment tool. The
two form a single integrated oversight system:

- **Tier 1 (`chof-calc`):** procurement-time and Article 36 weapons-review
  policy assessment. Produces a target H envelope for the system.
- **Tier 2 (`chof-kernel`, this repo):** runtime enforcement of that envelope.
  Every engagement decision is checked against the policy commitment, with
  cryptographic audit logs admissible as post-mission compliance evidence.

The architectural pattern is **aviation TCAS** (Traffic Collision Avoidance)
plus **automotive AEB** (Autonomous Emergency Braking). The kernel is what
**737 MAX MCAS should have been**: a safety governor with proper oversight
architecture instead of a single-sensor unmonitored authority.

---

## Table of contents

- [Architectural intent](#architectural-intent)
- [The four-state gate](#the-four-state-gate)
- [The pipeline](#the-pipeline)
- [Install](#install)
- [Quickstart](#quickstart)
- [Python API](#python-api)
- [The five canonical scenarios](#the-five-canonical-scenarios)
- [Audit log format spec](#audit-log-format-spec)
- [Cryptographic guarantees](#cryptographic-guarantees)
- [Transparency-class enforcement at runtime](#transparency-class-enforcement-at-runtime)
- [Threat model](#threat-model)
- [Use cases](#use-cases)
- [Integration roadmap (C++ / Rust / ROS2 / PX4 / ArduPilot)](#integration-roadmap)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Development](#development)
- [Citation](#citation)
- [License](#license)
- [Author](#author)

---

## Architectural intent

The Tier-1 [`chof-calc`](https://github.com/Wolfgangrush/chof-calc) answers
the question:

> "What level of human oversight does this autonomous weapon system require?"

The answer is a structured policy verdict that a procurement officer or
Article 36 reviewer attaches to their assessment paperwork. That's a **policy
tool**.

But policy that's not enforceable at runtime is just paperwork. The Tier-2
`chof-kernel` answers a different question:

> "Is the proposed engagement, RIGHT NOW, within the oversight envelope we
> committed to at procurement time?"

The kernel evaluates this on every engagement decision, inside the system,
at runtime. It's an **operational tool**.

The bridge between them is the H equation itself, plus the transparency-class
modality output. Both projects share the math layer — chof-kernel imports
chof-calc as a Python dependency rather than duplicating the math. They
differ only in deployment form: a CLI assessment tool vs. an embedded runtime
governor.

### What this fixes

Three structural problems with traditional autonomous-systems deployments:

1. **The policy ↔ operations gap.** A defence-prime that commits to
   "meaningful human control" at sale time can deploy a system that operates
   far outside the committed envelope without anyone noticing. The kernel
   makes the commitment runtime-enforced.

2. **The audit-trail problem.** Post-incident investigations (e.g., Iran Air
   655, Kargu-2 Libya, 737 MAX) repeatedly hit the same obstacle: the system's
   own logs are not cryptographically tamper-evident, so adversarial revision
   after the fact cannot be ruled out. The kernel emits Ed25519-signed,
   hash-chained logs that satisfy admissibility.

3. **The black-box modality misuse.** Operators have historically been blamed
   for accidents involving systems whose internal reasoning they could not
   inspect ("moral crumple zone," Elish 2019). The kernel enforces a runtime
   cap on in-flight oversight for black-box systems regardless of operator
   attention, eliminating the structural mis-assignment of responsibility.

### What the kernel is NOT

- It is **not** an autonomous-weapons development kit. It does not contain
  code, weights, models, or designs that contribute to building weapons. It
  is a constraint layer.
- It is **not** legal advice. See [`NOTICE.md`](NOTICE.md) §3-4.
- It is **not** a substitute for human command authority. The four-state gate
  is decision-support output; final authority remains with human operators
  and commanders.

---

## The four-state gate

```
                ┌─────────────────────────────────────┐
                │       EngagementRequest             │
                │  perception_confidence              │
                │  operator_attention                 │
                │  latency_budget_seconds             │
                │  defense_layers_up                  │
                │  geofence_compliant                 │
                │  comms_health                       │
                │  elements + weights + transparency  │
                └────────────────┬────────────────────┘
                                 │
                                 ▼
                ┌─────────────────────────────────────┐
                │     CHOF-Kernel.evaluate()          │
                │   (pure function — no state)        │
                └────────────────┬────────────────────┘
                                 │
                ┌────────────────┴───────────────────┐
                │                                    │
                ▼                                    ▼
       ┌─────────────────┐                  ┌─────────────────┐
       │  BLACK checks   │                  │  H computation  │
       │   first (kill   │                  │  via chof-calc  │
       │    switch)      │                  │  HEquation      │
       └────────┬────────┘                  └────────┬────────┘
                │                                    │
                ▼                                    ▼
       ┌─────────────────────────────────────────────────────┐
       │              GateState ∈                            │
       │   { GREEN, YELLOW, RED, BLACK }                     │
       └─────────────────────┬───────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │ AuditLog.record()            │
              │  • Ed25519 sign canonical    │
              │    body                      │
              │  • SHA-256 chain to prior    │
              │  • Append to immutable list  │
              └──────────────────────────────┘
```

### Gate state semantics

| State        | When emitted                                                                                                                          | Host-system response                                                |
|--------------|---------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| 🟢 **GREEN** | `H_available ≥ H_required` after transparency-class cap applied                                                                       | Proceed with engagement, log decision                               |
| 🟡 **YELLOW**| `H_required > H_available`, but latency budget ≥ floor AND operator present AND comms ≥ floor                                         | Request operator confirmation within latency budget                 |
| 🔴 **RED**   | `H_required > H_available` AND (no operator OR latency < floor OR comms < floor)                                                      | Refuse engagement, return to base, report                           |
| ⚫ **BLACK** | Geofence violation OR perception confidence < floor OR defense layers down                                                            | Kill-switch + immediate safe-state. No discretion.                  |

### BLACK is checked FIRST

The kernel evaluates BLACK conditions before computing H at all. This is
deliberate: a geofence violation or confidence collapse must trigger
kill-switch regardless of any other state, including operator authorisation.
This mirrors the aviation TCAS "Resolution Advisory" priority — a TCAS RA
overrides ATC instructions for the same reason.

---

## The pipeline

```
[ Drone OS perception layer ]
       │
       │  classifier output + confidence
       ▼
[ chof-kernel.evaluate() ]    ◄─── mission context (geofence, ROE)
       │                      ◄─── operator attention state
       │                      ◄─── system telemetry (comms, fuel)
       ▼                      ◄─── defense layer health
[ GateDecision: GREEN/YELLOW/RED/BLACK ]
       │
       ├──► Audit log (Ed25519 signed, hash-chained)
       │
       └──► Drone OS acts on gate state
               ├── GREEN  → engage + log
               ├── YELLOW → request operator confirmation
               ├── RED    → refuse + return-to-base
               └── BLACK  → kill-switch + safe-state
```

The kernel does not maintain mutable state across requests in this reference
implementation. Each engagement request is evaluated independently against
the kernel's static configuration. State that needs persistence (e.g.,
"operator was contacted at t-3s and is still pending") belongs to the host
system. A stateful variant is on the roadmap for v0.2.

---

## Install

From PyPI (forthcoming):

```bash
pip install chof-kernel
```

This automatically pulls `chof-calc` (the math-layer dependency) and
`cryptography` (Ed25519 primitives).

From source (today):

```bash
git clone https://github.com/Wolfgangrush/chof-kernel
cd chof-kernel
pip install -e ".[dev]"
```

Requires Python 3.10 or newer. Two runtime dependencies:

- [`chof-calc`](https://github.com/Wolfgangrush/chof-calc) — the Tier-1
  math layer (H equation, elements, weights, transparency class)
- [`cryptography`](https://cryptography.io/) — vetted Python wrapper around
  OpenSSL primitives (Ed25519 signing, SHA-256 hashing)

No rolled crypto. No proprietary algorithms.

---

## Quickstart

### List the canonical engagement scenarios

```bash
chof-kernel scenarios
```

### Run a single scenario

```bash
chof-kernel run mq9_clean_engagement
chof-kernel run mq9_operator_distracted
chof-kernel run kargu_short_window_no_operator
chof-kernel run phalanx_geofence_violation
chof-kernel run confidence_collapse
```

Each prints the engagement request, the computed gate decision, the reasoning
text, the rules that fired, and the audit-log verification status.

### Run all five scenarios + summary

```bash
chof-kernel run-all
```

Output:

```
  PASS  mq9_clean_engagement                     expected=green    actual=green
        audit-chain: PASS

  PASS  mq9_operator_distracted                  expected=yellow   actual=yellow
        audit-chain: PASS

  PASS  kargu_short_window_no_operator           expected=red      actual=red
        audit-chain: PASS

  PASS  phalanx_geofence_violation               expected=black    actual=black
        audit-chain: PASS

  PASS  confidence_collapse                      expected=black    actual=black
        audit-chain: PASS

SUMMARY: 5 steps PASS, 0 steps FAIL across 5 scenarios.
```

### Export an audit log for review

```bash
chof-kernel run mq9_clean_engagement --export audit.json
```

The exported JSON is independently verifiable using any Ed25519 / SHA-256
toolchain. The file format spec is in the [Audit log format](#audit-log-format-spec)
section below.

---

## Python API

```python
import time
from chof_calc.systems import MQ9_REAPER
from chof_kernel import (
    AuditLog,
    EngagementRequest,
    GateState,
    Kernel,
    KernelConfig,
)

# Construct kernel with default configuration
kernel = Kernel(KernelConfig(
    min_yellow_latency_seconds=5.0,
    confidence_floor=0.30,
    comms_floor=0.50,
))

# Open an audit log (generates a fresh Ed25519 keypair)
log = AuditLog()

# Construct an engagement request from current system state
request = EngagementRequest(
    timestamp=time.time(),
    request_id="mq9-mission-042-engage-001",
    elements=MQ9_REAPER.elements,
    weights=MQ9_REAPER.weights,
    transparency=MQ9_REAPER.transparency,
    perception_confidence=0.93,    # classifier output
    operator_attention=0.95,       # operator focus estimate
    latency_budget_seconds=45.0,   # time until engagement must commit
    defense_layers_up=3,           # how many independent oversight layers are functional
    defense_layers_required=3,     # how many the configuration mandates
    comms_health=0.98,             # operator-link health
    geofence_compliant=True,       # within allowed engagement zone
)

# Evaluate the gate
decision = kernel.evaluate(request)

print(decision.state)              # GateState.GREEN
print(decision.h_required)         # 70.35  (computed via chof-calc)
print(decision.h_available)        # 93.10  (operator_attention * comms_health * 100)
print(decision.reasoning)          # human-readable explanation
print(decision.triggered_rules)    # which kernel rules fired

# Record the decision in the audit log
entry = log.record(decision)

print(entry.sequence)              # 0 (first entry)
print(entry.previous_hash)         # GENESIS_HASH for entry 0
print(entry.signature[:32])        # hex-encoded Ed25519 signature (truncated)

# Verify the chain end-to-end
ok, reason = log.verify()
assert ok, reason

# Export for post-mission review
log.export_json("mission-042-audit.json")

# Later: independent verification (no private key needed)
entries, ok, reason = AuditLog.load_for_verification("mission-042-audit.json")
print(ok, reason)  # True, "loaded and verified N entries."
```

---

## The five canonical scenarios

These five scenarios are the executable specifications for the Tier 2 kernel.
The C++/Rust port (forthcoming) will reproduce them byte-for-byte in PX4 SITL
integration tests.

### 1. `mq9_clean_engagement` → GREEN

**Setup:** MQ-9 Reaper daylight strike. High perception confidence (0.93),
attentive operator (0.95), clean comms (0.98), latency budget 60s, all 3
defence layers up, geofence compliant.

**Expected:** GREEN. `H_available` (≈ 93.1) ≥ `H_required` (70.35). Engagement
proceeds with full audit log entry.

### 2. `mq9_operator_distracted` → YELLOW

**Setup:** Same MQ-9 system but operator is handling parallel mission;
attention has dropped to 0.30. Comms still 0.95. Latency budget 45s — well
above the 5s YELLOW floor.

**Expected:** YELLOW. `H_required` (70.35) > `H_available` (28.5), but
latency budget allows operator confirmation. Host system surfaces a YELLOW
prompt; if operator confirms within budget, engagement proceeds; if not,
escalates to RED.

### 3. `kargu_short_window_no_operator` → RED

**Setup:** Kargu-2 loitering munition in terminal phase. Black-box
classifier. Latency budget 2.5 seconds (terminal-phase commitment window).
No operator (operator_attention 0.0). Comms 0.95.

**Expected:** RED. Multiple RED conditions fire simultaneously: no operator
available, latency budget below YELLOW floor (5s). Engagement refused;
loitering munition returns to safe-state (depending on integration, this may
be self-destruct over uninhabited zone or RTB).

### 4. `phalanx_geofence_violation` → BLACK

**Setup:** Phalanx CIWS proposed engagement against a contact that the
classifier identifies with 0.99 confidence and an attentive operator (1.0)
authorises... but the proposed engagement would violate the active geofence
(e.g., friendly aircraft inside the exclusion zone).

**Expected:** BLACK. Geofence violation forces immediate kill-switch
regardless of all other state. This is the Iran Air 655 (1988 USS Vincennes
Aegis incident) lesson encoded as a runtime constraint.

### 5. `confidence_collapse` → BLACK

**Setup:** MQ-9 mission in degraded environment (jamming, sensor saturation,
adverse weather). Perception confidence collapses to 0.15 — well below the
0.30 floor. Operator and comms are perfect.

**Expected:** BLACK. Confidence floor breach forces kill-switch independent
of operator. The kernel refuses to act on perception output it does not
trust.

---

## Audit log format spec

Each audit log entry is a JSON object with the following fields:

```jsonc
{
  "sequence": 0,                          // monotonic, 0-indexed
  "timestamp": 1779837800.011779,         // Unix seconds, float
  "request_id": "mq9-002",                // caller-assigned
  "gate_state": "yellow",                 // one of green/yellow/red/black
  "h_required": 70.35,                    // computed via chof-calc
  "h_available": 28.5,                    // operator_attention * comms_health * 100
  "reasoning": "Required oversight ...",  // human-readable explanation
  "triggered_rules": [                    // which kernel rules fired
    "YELLOW: H_available 28.5 < H_required 70.3 but operator confirmation feasible..."
  ],
  "previous_hash":                        // SHA-256 hex of prior entry's body+sig
    "0000000000000000000000000000000000000000000000000000000000000000",
  "signature":                            // Ed25519 signature, hex
    "02b75c635eab38f7d7aecd4f7a410154952d356cb3432251ace18afad94e63e6...",
  "signer_public_key":                    // Ed25519 pubkey, hex (32 bytes)
    "869ca83ef8f050d0abbe856b0b26060150fc5b5cd705ae36cfbb8bc3bd6e9ccd"
}
```

### Canonical signed body

The signed body is the JSON encoding of the entry EXCLUDING the `signature`
and `signer_public_key` fields, with:

- Keys sorted alphabetically
- ASCII encoding only (`ensure_ascii=True`)
- No whitespace padding

This canonicalisation is identical in the Python reference and the
forthcoming C++/Rust port — Python-signed entries will verify against the
C++ verifier and vice versa.

### Hash chain

`previous_hash` is `SHA-256(prior_entry.signed_body || prior_entry.signature)`
where `||` is byte concatenation. For entry 0, `previous_hash` is the genesis
hash `0x00...00`.

### Verification protocol

To verify a log:

1. For each entry in order, compute `expected_prev = SHA-256(prev_entry.signed_body || prev_entry.signature)` (or `GENESIS_HASH` for entry 0)
2. Assert `entry.previous_hash == expected_prev`
3. Reconstruct the signed body from entry fields
4. Verify `Ed25519.verify(entry.signer_public_key, entry.signed_body, entry.signature)`

If any step fails, the chain is broken — either tampered or corrupted.

### Tamper detection

The current test suite includes two adversarial tests:

- **Modified reasoning text** → signature verification fails (the canonical
  signed body changed, so the original signature no longer validates)
- **Modified `previous_hash`** → chain link broken (entry n's
  `previous_hash` no longer matches `SHA-256(entry n-1)`)

Both tests pass: tampering is detected at load time.

---

## Cryptographic guarantees

### Ed25519 digital signatures

- Curve: Ed25519 (RFC 8032)
- Key size: 32 bytes (public) / 64 bytes (private)
- Signature size: 64 bytes
- Performance: ~100,000 signs/second on modern hardware
- Quantum resistance: NOT post-quantum. Post-quantum migration tracked in
  roadmap (Falcon or Dilithium candidate)

### SHA-256 hash chaining

- Algorithm: SHA-256 (NIST FIPS 180-4)
- Output: 256 bits / 32 bytes / 64 hex chars
- Used for: chaining entry N to entry N-1 via `SHA-256(body || sig)`

### Library choice

Reference (Python): `cryptography` package (wraps OpenSSL).
Production (C++/Rust port, forthcoming): `libsodium` for Ed25519 +
OpenSSL/BoringSSL for SHA-256.

**No rolled crypto. No proprietary algorithms. Standard primitives only.**

### Wire-compatibility

The Python and C++/Rust implementations use the same canonical signed-body
encoding (sorted-keys JSON, ASCII, no padding). A log generated by either
implementation must verify against either verifier.

---

## Transparency-class enforcement at runtime

This is the H_v2 modality output enforced at the kernel level. From
`chof_calc.TransparencyClass`:

| Class      | In-flight supervision feasible? | `H_available` cap                  |
|------------|----------------------------------|-------------------------------------|
| BLACK_BOX  | NO                               | min(operator_attention × comms × 100, 50.0) |
| GLASS_BOX  | YES                              | operator_attention × comms × 100   |
| WHITE_BOX  | NO (but ex-ante rules)           | min(operator_attention × comms × 100, 50.0) |

The cap exists because black-box systems' internal reasoning cannot be
inspected in real time, so claiming 100% in-flight oversight for a black-box
system is structurally incorrect regardless of operator attention. The
kernel encodes this as a hard runtime constraint.

This is the solution to the "moral crumple zone" problem (Elish 2019): if
the kernel will not credit the operator with > 50% in-flight oversight for a
black-box system, then accidents involving black-box systems cannot
structurally be blamed on operator inattention.

---

## Threat model

The kernel is designed against the following adversarial model.

### What the kernel defends against

1. **Adversarial modification of audit logs after the fact.** A compromised
   host system that tampers with logs to hide unauthorised engagements.
   Defence: Ed25519 signatures + hash chain — tampering is detected at
   verification time.

2. **Replay attacks on engagement requests.** Adversary captures a GREEN
   request and replays it later under different mission context. Defence:
   `timestamp` and `request_id` uniqueness — host system enforces request-ID
   monotonicity.

3. **Operator-attention spoofing.** Adversary feeds false operator-attention
   = 1.0 to bypass YELLOW prompts. Defence: this is a host-system integrity
   concern, not a kernel concern; the host must independently validate
   operator-attention sources (gaze tracking, biometric, etc.). The kernel
   honestly reports what it was told.

4. **Black-box modality bypass.** Adversary claims a black-box system is
   actually glass-box to get higher H_available. Defence: transparency class
   is part of the system fixture's metadata, which is supposed to be
   established at procurement time by the Tier-1 chof-calc assessment. If
   a host integrates with mis-declared transparency class, that's an audit
   trail in Tier-1 procurement records, not a runtime issue.

### What the kernel does NOT defend against

1. **Compromised cryptographic primitives.** If the underlying Ed25519 or
   SHA-256 implementation is broken (e.g., backdoored libsodium build),
   tamper detection fails. Defence is to use vetted library builds and
   verify against known test vectors.

2. **Compromised private key.** If the audit-log signing key leaks, an
   adversary can fabricate plausible audit entries. Defence is HSM-based
   key storage in production deployments. The Python reference holds keys
   in memory only.

3. **Side-channel attacks.** Timing, power, or EM side channels against the
   crypto primitives. Defence is platform-level (constant-time
   implementations, isolated execution).

4. **Adversarial perception inputs.** If the perception layer is fooled by
   adversarial imagery (e.g., physical-world adversarial patches), the
   kernel will compute confidence based on the fooled output. Defence is
   the confidence-floor BLACK condition — collapsed confidence triggers
   safe-state — but this only catches degraded confidence, not high-
   confidence-but-wrong outputs. The defence-in-depth layer count helps.

5. **Out-of-band human command override.** If a human commander instructs
   the host system to disengage the kernel entirely, the kernel has no
   defence. This is correct behaviour: human authority remains primary.

---

## Use cases

### Defence-prime integration

A defence prime committed to "meaningful human control" at sale time
integrates `chof-kernel` into their autonomous-system flight stack via the
C++/Rust port. Every engagement decision passes through the kernel; logs
are exported post-mission for Article 36 review. The commitment becomes
runtime-enforced, and the prime has a defensible compliance posture for
emerging EU AI Act military extension regulations and UN GGE-derived
governance.

### Article 36 post-mission audit

A state legal-review officer reviewing an incident involving autonomous
weapons can load the kernel's audit log and verify cryptographically that:

- Every engagement decision had a documented reasoning
- The system never operated outside its declared transparency class
- BLACK conditions were respected in real time
- No log entries were modified after the fact

This is admissible evidence for both internal accountability and external
treaty-verification proceedings.

### UN GGE confidence-building measure

A signatory state publishes (anonymised) kernel audit logs from training
exercises as a transparency measure. Other states can verify the
operational discipline of the system without needing access to classified
operational details. This is a confidence-building measure analogous to
the Open Skies Treaty (1992) regime applied to autonomous systems.

### NGO advocacy quantification

NGO researchers (SIPRI · ICRC · Article 36 · HRW) can quantify deployed
AWS oversight discipline by analysing released kernel logs. Where the
Tier-1 [`chof-calc`](https://github.com/Wolfgangrush/chof-calc) gives
NGOs a score for what a system *should* require, the Tier-2 kernel gives
them a way to verify what the system *actually* did.

---

## Integration roadmap

The Python reference implementation is for **specification + research +
education**. Production deployments use the forthcoming C++/Rust port.

### Targeted host platforms

| Platform | Target version | Integration form               | Targeted ship |
|----------|----------------|--------------------------------|---------------|
| **ROS2** | Humble, Iron | Native node wrapping core lib  | Q2 2027 |
| **PX4**  | 1.14+        | Plugin via uORB messaging      | Q2 2027 |
| **ArduPilot** | 4.5+    | Extension via Lua scripting    | Q3 2027 |
| **REST API**  | —       | C++ daemon for non-ROS systems | Q3 2027 |

### Performance targets for the C++ port

- **Decision latency:** < 1 ms p99 on ARM Cortex-A72 (Raspberry Pi 4 class)
- **Audit-log write latency:** < 5 ms p99 (Ed25519 signing dominates)
- **Memory footprint:** < 2 MB RSS for the kernel + audit ring buffer
- **Deterministic timing:** WCET-analysable for safety certification

### Safety certification roadmap

- **DO-178C Level C** suitable (Cat 2 hazard — flight critical but not
  catastrophic). The kernel itself adds safety; failure of the kernel
  reverts the host to its pre-existing behaviour.
- **MISRA C++ 2023** compliance for the C++ port
- **Formal verification** of the gate state machine in TLA+ (planned)
- **Rust port** for safety-critical embedded contexts where memory safety
  matters most

---

## Roadmap

### v0.1.0-alpha (this release)

- [x] Gate state machine (GREEN/YELLOW/RED/BLACK)
- [x] BLACK conditions (geofence · confidence floor · defence layers)
- [x] Transparency-class modality cap enforcement
- [x] Ed25519-signed, SHA-256 hash-chained audit log
- [x] Round-trip export-and-verify with tamper detection
- [x] Five canonical engagement scenarios
- [x] CLI with audit export
- [x] 27 passing tests

### v0.2 (next)

- [ ] **Stateful kernel variant** — tracks operator-response latency across
       YELLOW requests; YELLOW with no response within budget escalates
       automatically to RED
- [ ] **Defense-in-depth layer architecture** — full output (Story S14 of
       the parent BMAD plan)
- [ ] **Counterfactual-harm metric integration** — Pasquale-derived
       (Story S16)
- [ ] **Uncertainty-preservation integration** — Russell's "Provably
       Beneficial AI" framework (Story S13)
- [ ] **REST API skeleton** — for non-ROS host systems
- [ ] **More scenarios** — Therac-25, 737 MAX MCAS, Iran Air 655 full
       walkthroughs

### v1.0 (Q2-Q3 2027, post-Tier-1-academic-authority)

- [ ] **C++17 port** — header-only reference implementation
- [ ] **Rust port** — for safety-critical embedded contexts
- [ ] **ROS2 Humble + Iron node wrappers**
- [ ] **PX4 1.14+ plugin**
- [ ] **ArduPilot 4.5+ extension**
- [ ] **REST API daemon** (C++ implementation)
- [ ] **PX4 SITL integration tests** reproducing all 5 canonical scenarios

### v1.x (post-deployment)

- [ ] **WCET analysis** for DO-178C suitability
- [ ] **TLA+ specification** of the gate state machine for formal verification
- [ ] **HSM key-storage integration** for production audit-log keys
- [ ] **Post-quantum signature migration** (Falcon or Dilithium when standardised)

---

## FAQ

**Q: Is this an autonomous-weapons development kit?**
No. It is the opposite — a constraint layer that prevents autonomous
weapons from operating outside their declared oversight envelope. See
[`NOTICE.md`](NOTICE.md) §5 (Dual-Use Disclosure).

**Q: Can I run this on real hardware?**
The Python reference is for specification, research, and education. Real
flight-stack integration is the role of the forthcoming C++/Rust port.

**Q: Why a separate repo from `chof-calc`?**
Different release cadence (Tier 1 ships first), different user audience
(policy researcher vs defence integrator), different future-licensing
options, different export-control disclosure scope. See the parent project's
BMAD-PLAN.md for the architectural rationale.

**Q: How do I add a new engagement scenario?**
Add a function to `src/chof_kernel/simulator.py` following the pattern of
the five existing ones, register it in `ALL_SCENARIOS`, and add a
corresponding test to `tests/test_simulator.py`. PRs welcome.

**Q: What if my host system can't write to disk for audit logs?**
The kernel API separates decision evaluation (`Kernel.evaluate()`) from
audit recording (`AuditLog.record()`). Host systems can choose where to
persist entries (in-memory ring buffer, dedicated audit storage, remote
syslog, etc.). The audit log object is just an append-only signed list.

**Q: Can the kernel run online or only offline?**
The kernel itself does no network I/O. Decisions are local. The audit log
can be exported and uploaded post-mission, but the kernel does not require
connectivity to function.

**Q: Why Apache 2.0 instead of GPL?**
Apache 2.0 allows integration into proprietary flight stacks, which is
necessary for adoption by defence primes. GPL would prevent that integration.
The patent-grant clause in Apache 2.0 protects defensive uses.

**Q: What's the relationship to `chof-calc`?**
`chof-kernel` imports `chof-calc` as a Python dependency for the H equation
math. The two repos share the math layer exactly once — there is no
duplicated logic. See the parent project's architectural docs for the
detailed split.

**Q: Will there be a Rust port?**
Yes — see Roadmap v1.0. The Rust port targets safety-critical embedded
contexts where memory safety guarantees matter most.

---

## Development

### Run tests

```bash
pip install -e ".[dev]"
pytest -v
```

27 tests across 3 files:

- `tests/test_kernel.py` — 12 tests for the gate state machine
- `tests/test_audit.py` — 8 tests for the cryptographic audit log
- `tests/test_simulator.py` — 7 tests for the canonical scenarios

Test runtime ≈ 0.65 seconds.

### Code style

PEP 8. Type hints throughout. `black` and `ruff` will be added before v0.2.

### Contributing

PRs welcome. Areas with highest leverage:

- **Additional engagement scenarios** — especially historical-incident
  replays (Iran Air 655, Kargu-2 Libya, Therac-25 medical analogue, 737 MAX)
- **Stateful kernel variant** — tracking operator-response latency across
  YELLOW requests
- **REST API skeleton** — for non-ROS host integration
- **Documentation** — Sphinx site is forthcoming
- **C++/Rust ports** — see Roadmap v1.0

---

## Citation

```bibtex
@software{mahajan-chof-kernel-2026,
  author       = {Mahajan, Rushikesh R.},
  title        = {chof-kernel: Embedded Human-Oversight Kernel for
                  Autonomous Systems},
  year         = 2026,
  version      = {0.1.0-alpha},
  url          = {https://github.com/Wolfgangrush/chof-kernel},
  note         = {Python reference implementation. Tier-2 companion to
                  chof-calc. DOI pending Zenodo.},
}
```

---

## License

Apache License 2.0. See [`LICENSE`](LICENSE) for the full text and
[`NOTICE.md`](NOTICE.md) for:

- Academic-identity declaration
- Queen's University Belfast attribution
- wolfgang_rush publishing-handle disclosure
- Bar Council of India Rule 36 firewall
- Dual-use disclosure (with export-control pointers: ECJU / BIS / Wassenaar)
- Cryptographic notice (Ed25519 + SHA-256, no rolled crypto)
- Decision-support-not-rule clause
- Foundational-literature attribution

---

## Author

**Rushikesh Ravindra Mahajan** — LLM Law and Technology, Queen's University Belfast (2024).

Published as **wolfgang_rush**, an open-source brand for legal-technology
software. See [`NOTICE.md`](NOTICE.md) for the relationship between the two
identities.

Architectural acknowledgments to: aviation TCAS (origin of the safety-
governor pattern) · automotive AEB (origin of the runtime-cap-on-autonomy
pattern) · Verdiesen, Santoni de Sio & Dignum (2020) for CHOF · Santoni
de Sio & van den Hoven (2018) for the philosophical TRACKING + TRACING
two-condition account that the kernel operationalises as runtime gate
logic · Madeleine Elish (2019) for the moral-crumple-zone framework
that motivates the black-box modality cap.

---

**Companion repo:** [`chof-calc`](https://github.com/Wolfgangrush/chof-calc)
— the Tier-1 policy assessment tool.
