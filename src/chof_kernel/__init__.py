"""
chof-kernel — Embedded human-oversight kernel for autonomous systems.

This is the Python reference implementation of the CHOF-Kernel — a tactical
safety governor that sits inside an autonomous system's flight stack,
between the perception/classifier output and the engagement-decision
module. Architectural pattern: aviation TCAS + automotive AEB. The kernel
is what 737 MAX MCAS should have been: a safety governor with proper
oversight architecture.

Production deployments use a C++/Rust port that compiles into ROS2 nodes,
PX4 plugins, and ArduPilot extensions (forthcoming Q2-Q3 2027). This
Python implementation is the reference for the math layer, the gate state
machine, and the audit-log format.

Pipeline:

  perception confidence + mission context + system telemetry + operator
  attention state
                |
                v
        CHOF-Kernel evaluation
                |
                v
        Gate state in {GREEN, YELLOW, RED, BLACK}
                |
                v
        Drone OS acts on gate state + writes Ed25519-signed audit entry

Public API:
    chof_kernel.Kernel             — the state machine
    chof_kernel.GateState          — GREEN / YELLOW / RED / BLACK
    chof_kernel.EngagementRequest  — input to the kernel
    chof_kernel.GateDecision       — output of the kernel
    chof_kernel.AuditLog           — Ed25519-signed tamper-evident log
"""

from chof_kernel.audit import AuditEntry, AuditLog
from chof_kernel.kernel import (
    EngagementRequest,
    GateDecision,
    GateState,
    Kernel,
    KernelConfig,
)

__version__ = "0.1.0-alpha"
__all__ = [
    "AuditEntry",
    "AuditLog",
    "EngagementRequest",
    "GateDecision",
    "GateState",
    "Kernel",
    "KernelConfig",
    "__version__",
]
