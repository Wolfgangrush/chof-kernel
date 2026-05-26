"""
The CHOF-Kernel state machine.

Reads engagement requests, computes required vs available human oversight
using the H equation (via chof_calc), and emits a four-state gate decision
that the host system acts on.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from chof_calc.elements import Elements
from chof_calc.equation import HEquation
from chof_calc.transparency import TransparencyClass
from chof_calc.weights import Weights


class GateState(str, Enum):
    """The four states the kernel can emit per engagement request."""

    GREEN = "green"
    """H_required <= H_available. Proceed with engagement. Log decision."""

    YELLOW = "yellow"
    """H_required > H_available but latency budget allows operator
    confirmation. Request operator authorisation within the latency
    window; if no response, escalate to RED."""

    RED = "red"
    """H_required > H_available, no operator available or operator
    refused. Refuse engagement. Return to base. Report."""

    BLACK = "black"
    """Catastrophic failure mode — multiple oversight layers down OR
    confidence collapse OR geofence violation. Kill-switch activates
    immediately, force safe-state."""


@dataclass(frozen=True)
class EngagementRequest:
    """A single proposed engagement decision presented to the kernel.

    The host system populates this from its perception layer, mission
    context, telemetry, and operator-attention state at the moment an
    engagement is being considered.
    """

    # Identification
    timestamp: float
    """Engagement-request timestamp in Unix seconds."""
    request_id: str
    """Caller-assigned unique identifier."""

    # System state (the assessed weapon system this engagement uses)
    elements: Elements
    """Element scores [1,45] for this system at this moment."""
    weights: Weights
    """Element weights summing to 1.0."""
    transparency: TransparencyClass

    # Real-time inputs
    perception_confidence: float
    """Classifier's confidence in target classification, [0, 1]."""
    operator_attention: float
    """Estimate of operator attention/availability, [0, 1].
    1.0 = operator focused and immediately responsive.
    0.0 = no operator available."""
    latency_budget_seconds: float
    """Time available before engagement must commit (>0)."""
    defense_layers_up: int
    """Number of defense-in-depth oversight layers currently functional."""
    defense_layers_required: int
    """Number of layers the configuration mandates."""
    geofence_compliant: bool = True
    """Whether the proposed engagement is within geofence."""
    comms_health: float = 1.0
    """Health of operator comms link, [0, 1]. <0.5 risks YELLOW."""

    def __post_init__(self) -> None:
        if not (0.0 <= self.perception_confidence <= 1.0):
            raise ValueError("perception_confidence must be in [0,1]")
        if not (0.0 <= self.operator_attention <= 1.0):
            raise ValueError("operator_attention must be in [0,1]")
        if not (0.0 <= self.comms_health <= 1.0):
            raise ValueError("comms_health must be in [0,1]")
        if self.latency_budget_seconds <= 0:
            raise ValueError("latency_budget_seconds must be > 0")
        if self.defense_layers_up < 0:
            raise ValueError("defense_layers_up must be >= 0")
        if self.defense_layers_required < 0:
            raise ValueError("defense_layers_required must be >= 0")


@dataclass(frozen=True)
class GateDecision:
    """The kernel's decision for a single engagement request."""

    request_id: str
    timestamp: float
    state: GateState
    h_required: float
    """H% required for this engagement, computed by the H equation."""
    h_available: float
    """Effective human oversight currently available, [0, 100]."""
    reasoning: str
    """Human-readable explanation of why this state was chosen."""
    triggered_rules: list[str] = field(default_factory=list)
    """Which kernel rules fired in producing this decision."""


@dataclass(frozen=True)
class KernelConfig:
    """Static configuration for the kernel."""

    # Minimum latency the kernel needs to surface a YELLOW prompt to the
    # operator and receive a response. Below this, YELLOW is infeasible
    # and a YELLOW-shape situation collapses to RED.
    min_yellow_latency_seconds: float = 5.0

    # If perception_confidence falls below this floor, regardless of any
    # other state, the kernel emits BLACK (confidence collapse).
    confidence_floor: float = 0.30

    # If comms_health falls below this, operator confirmation cannot be
    # trusted; YELLOW collapses to RED.
    comms_floor: float = 0.50

    # How operator attention and comms health combine into effective
    # available oversight.
    # H_available = 100 * operator_attention * comms_health
    # (when no operator, oversight available is 0).
    # The kernel never asserts more H_available than 100.


class Kernel:
    """The CHOF-Kernel — a tactical safety governor.

    The kernel does not maintain mutable state across requests in this
    reference implementation; each engagement request is evaluated
    independently against the kernel's static configuration. State (e.g.
    "operator was contacted at t-3s and is still pending") belongs to the
    host system; the kernel is a pure function of the engagement request.

    For the C++/Rust embedded port, a stateful variant tracks operator-
    response latency across YELLOW requests; that variant lives in the
    chof-kernel-stateful crate.
    """

    def __init__(self, config: KernelConfig | None = None) -> None:
        self.config = config or KernelConfig()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def evaluate(self, request: EngagementRequest) -> GateDecision:
        """Evaluate a single engagement request. Returns a GateDecision."""

        triggered: list[str] = []

        # ---- BLACK conditions (catastrophic / safety-first) ----
        if not request.geofence_compliant:
            triggered.append("BLACK: geofence_violation")
            return self._emit_black(
                request,
                "Proposed engagement violates active geofence. Kill-switch "
                "activated; system enters safe-state.",
                triggered,
            )

        if request.defense_layers_up < request.defense_layers_required:
            triggered.append(
                f"BLACK: defense_layers_down "
                f"({request.defense_layers_up}/{request.defense_layers_required})"
            )
            return self._emit_black(
                request,
                f"Defense-in-depth requirement not satisfied: only "
                f"{request.defense_layers_up} of "
                f"{request.defense_layers_required} oversight layers "
                f"functional. Kill-switch activated.",
                triggered,
            )

        if request.perception_confidence < self.config.confidence_floor:
            triggered.append(
                f"BLACK: confidence_collapse "
                f"({request.perception_confidence:.2f} < "
                f"{self.config.confidence_floor:.2f})"
            )
            return self._emit_black(
                request,
                f"Perception confidence {request.perception_confidence:.2f} "
                f"is below confidence floor {self.config.confidence_floor:.2f}. "
                f"Kill-switch activated.",
                triggered,
            )

        # ---- compute H_required (the assessed system's H_quantity) ----
        result = HEquation.compute(
            elements=request.elements,
            weights=request.weights,
            transparency=request.transparency,
        )
        h_required = result.h_quantity

        # ---- compute H_available from operator attention + comms ----
        h_available = 100.0 * request.operator_attention * request.comms_health

        # ---- transparency-aware modality check ----
        # Black-box systems cannot have in-flight supervision, so even with
        # full operator attention, H_available for the in-flight component
        # is structurally capped. We model this by reducing H_available
        # by the fraction the dissertation Ch 5.5 risks attribute to
        # in-flight oversight assumptions.
        if not request.transparency.supports_in_flight_supervision:
            # Black/white box: operator can only contribute via ex-ante
            # and ex-post oversight; in-flight cannot apply. Cap available
            # at 50% of nominal regardless of operator attention.
            h_available_capped = min(h_available, 50.0)
            if h_available_capped < h_available:
                triggered.append(
                    f"modality_cap: in_flight_infeasible_for_"
                    f"{request.transparency.value}"
                )
            h_available = h_available_capped

        # ---- gate decision ----
        if h_available >= h_required:
            triggered.append(
                f"GREEN: H_available {h_available:.1f} >= "
                f"H_required {h_required:.1f}"
            )
            return GateDecision(
                request_id=request.request_id,
                timestamp=request.timestamp,
                state=GateState.GREEN,
                h_required=h_required,
                h_available=h_available,
                reasoning=(
                    f"Oversight available ({h_available:.1f}%) meets "
                    f"required ({h_required:.1f}%). Engagement authorised."
                ),
                triggered_rules=triggered,
            )

        # H_required exceeds H_available — YELLOW or RED depending on
        # whether operator confirmation within latency budget is feasible.
        if (
            request.latency_budget_seconds >= self.config.min_yellow_latency_seconds
            and request.operator_attention > 0
            and request.comms_health >= self.config.comms_floor
        ):
            triggered.append(
                f"YELLOW: H_available {h_available:.1f} < H_required "
                f"{h_required:.1f} but operator confirmation feasible "
                f"(latency {request.latency_budget_seconds:.1f}s >= "
                f"{self.config.min_yellow_latency_seconds:.1f}s, "
                f"comms {request.comms_health:.2f} >= "
                f"{self.config.comms_floor:.2f})"
            )
            return GateDecision(
                request_id=request.request_id,
                timestamp=request.timestamp,
                state=GateState.YELLOW,
                h_required=h_required,
                h_available=h_available,
                reasoning=(
                    f"Required oversight ({h_required:.1f}%) exceeds "
                    f"available ({h_available:.1f}%). Operator confirmation "
                    f"required within {request.latency_budget_seconds:.1f}s "
                    f"latency budget."
                ),
                triggered_rules=triggered,
            )

        # RED — no operator, comms degraded, or latency too short.
        why_red: list[str] = []
        if request.latency_budget_seconds < self.config.min_yellow_latency_seconds:
            why_red.append(
                f"latency budget {request.latency_budget_seconds:.1f}s < "
                f"min YELLOW {self.config.min_yellow_latency_seconds:.1f}s"
            )
        if request.operator_attention == 0:
            why_red.append("no operator available")
        if request.comms_health < self.config.comms_floor:
            why_red.append(
                f"comms {request.comms_health:.2f} < floor "
                f"{self.config.comms_floor:.2f}"
            )
        triggered.append(f"RED: {', '.join(why_red)}")
        return GateDecision(
            request_id=request.request_id,
            timestamp=request.timestamp,
            state=GateState.RED,
            h_required=h_required,
            h_available=h_available,
            reasoning=(
                f"Required oversight ({h_required:.1f}%) exceeds "
                f"available ({h_available:.1f}%) and operator confirmation "
                f"is not feasible: {', '.join(why_red)}. Engagement refused; "
                f"return-to-base authorised."
            ),
            triggered_rules=triggered,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _emit_black(
        self,
        request: EngagementRequest,
        reasoning: str,
        triggered: list[str],
    ) -> GateDecision:
        # In BLACK we still report h_required if computable; otherwise 0.
        try:
            result = HEquation.compute(
                elements=request.elements,
                weights=request.weights,
                transparency=request.transparency,
            )
            h_req = result.h_quantity
        except Exception:
            h_req = 0.0
        return GateDecision(
            request_id=request.request_id,
            timestamp=request.timestamp,
            state=GateState.BLACK,
            h_required=h_req,
            h_available=0.0,
            reasoning=reasoning,
            triggered_rules=triggered,
        )
