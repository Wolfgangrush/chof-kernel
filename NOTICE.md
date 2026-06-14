# NOTICE

**chof-kernel** — Embedded human-oversight kernel for autonomous systems.

Python reference implementation. Production deployments use the C++/Rust
port (forthcoming Q2-Q3 2027) for ROS2 / PX4 / ArduPilot integration.

Copyright 2026 Rushikesh Ravindra Mahajan.

Licensed under the Apache License, Version 2.0 (see `LICENSE`).

---

## 1. Authorship and Relationship to chof-calc

This kernel is the Tier-2 companion to the Tier-1 assessment tool
`chof-calc` and depends on it for the H equation math. Both build on:

> Mahajan, R. R. (2024). *What Balance Between Human Oversight and Machine
> Autonomy Is Necessary To Uphold Ethical Standards in Warfare, and How
> Can This Balance Be Legally Codified and Enforced.* LLM Dissertation,
> Queen's University Belfast, School of Law.

This Python implementation is the REFERENCE implementation of the kernel's
state machine + audit-log format. It is NOT intended for production
deployment in flight stacks. Production deployment uses the C++/Rust port,
which mirrors the algorithms here but adds:
- ROS2 node wrapper
- PX4 plugin
- ArduPilot extension
- REST API for non-ROS systems
- Real-time deterministic timing guarantees

---

## 2. Author Identity Declaration

This is the author's **academic** identity. The publishing handle for this open-source work is **wolfgang_rush**, an
open-source brand under which the author releases legal-technology
software. The real-identity accountability declared in this NOTICE attaches
to the author personally and is not displaced by the use of a publishing
handle.

---

## 3. Bar Council of India Rule 36 Firewall

The Bar Council of India Rules, Chapter II, Part VI, Section IV, Rule 36
prohibits Indian advocates from soliciting work or advertising legal
services. This software:

1. Is published as **academic and research software** under an open-source
   licence. It is *not* a legal-services offering.
2. Is **freely distributed** and audience-neutral.
3. Contains **no advertising of legal services**.
4. Is **explicitly not legal advice**. The kernel's gate decisions are
   decision-support outputs derived from a multi-criteria model. They do
   not constitute legal opinion on any specific autonomous weapon system,
   deployment scenario, or jurisdictional question.

---

## 4. Decision-Support Kernel — NOT a Definitive Rule

Consistent with the parent project's `chof-calc` NOTICE §4, this kernel
is a **decision-support tool**, NOT a definitive rule. The four-state gate
(GREEN/YELLOW/RED/BLACK) is a recommendation produced by a multi-criteria
algorithm. Operational deployment decisions in any autonomous-systems
context must remain subject to:

- Human commander oversight at the appropriate level
- Mission-specific legal review (Article 36 Geneva AP I weapons reviews)
- Real-time intelligence integration
- The legal framework of the deploying state

The audit log is a tamper-evident record of the kernel's decisions to
support post-mission review; it is NOT a substitute for command
accountability.

---

## 5. Dual-Use Disclosure — IMPORTANT

This software is an oversight kernel that *constrains* the behaviour of
autonomous systems. Its purpose is to make autonomous systems SAFER by
making the cost of choosing less-safe oversight options visible AT
RUNTIME. The software is NOT an autonomous-weapon-systems development kit;
it does not contain code, weights, models, or designs that contribute to
the development or manufacture of weapon systems themselves.

However, because the kernel is designed to integrate into autonomous-
systems flight stacks, integrators should verify compliance with any
applicable export-control regimes in their jurisdiction:

- **UK ECJU** — Goods Checker (20-min screen)
- **US BIS** — EAR Commerce Control List entries on autonomous systems
- **Wassenaar Arrangement** signatories — dual-use category 4
- **EU dual-use regulation** — Regulation (EU) 2021/821

The author recommends running an export-control classification on any
production integration of this kernel before deployment.

---

## 6. Cryptographic Notice

The audit log uses **Ed25519** digital signatures and **SHA-256** hash
chaining. Both are widely available, vetted cryptographic primitives. The
reference implementation uses Python's `cryptography` library (which wraps
OpenSSL); the production C++/Rust port uses libsodium (Ed25519) +
OpenSSL/BoringSSL (SHA-256).

No rolled crypto. No proprietary algorithms. The audit log format is
designed to be independently verifiable using standard tools.

---

## 7. Attribution to Foundational Literature

The kernel's design draws on:

- The H equation methodology from the parent project `chof-calc`
- Aviation TCAS (Traffic Collision Avoidance System) architectural pattern
- Automotive AEB (Autonomous Emergency Braking) governor pattern
- Verdiesen, Santoni de Sio & Dignum (2020) — CHOF framework
- Santoni de Sio & van den Hoven (2018) — TRACKING + TRACING two-condition
  test, which the kernel operationalises as runtime gate logic

The kernel is what 737 MAX MCAS should have been: a safety governor with
proper oversight architecture.

---

## 8. Reporting Issues

Bug reports, methodology critique, academic correspondence:
<https://github.com/wolfgang-rush/chof-kernel/issues>.

Security vulnerability disclosure: see `SECURITY.md` (forthcoming).
