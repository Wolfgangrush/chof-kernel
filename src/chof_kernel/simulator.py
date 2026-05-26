"""
Engagement scenario simulator.

Replays synthetic engagement sequences through the kernel + audit log to
demonstrate how each gate state arises. The same patterns will be
replayed by the C++/Rust kernel in PX4 SITL integration tests in the
forthcoming Tier 2 v0.2 release.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from chof_calc.systems import KARGU_2, MQ9_REAPER, PHALANX

from chof_kernel.audit import AuditLog
from chof_kernel.kernel import EngagementRequest, GateState, Kernel


@dataclass(frozen=True)
class ScenarioStep:
    label: str
    request: EngagementRequest
    expected_state: GateState


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    steps: list[ScenarioStep]


def scenario_mq9_clean_engagement() -> Scenario:
    """MQ-9 daylight strike with operator fully attentive."""
    return Scenario(
        name="mq9_clean_engagement",
        description=(
            "MQ-9 Reaper daylight strike: high confidence, attentive "
            "operator, clean comms, healthy defense layers, geofence-OK."
        ),
        steps=[
            ScenarioStep(
                label="t+0  high-confidence target acquisition",
                request=EngagementRequest(
                    timestamp=time.time(),
                    request_id="mq9-001",
                    elements=MQ9_REAPER.elements,
                    weights=MQ9_REAPER.weights,
                    transparency=MQ9_REAPER.transparency,
                    perception_confidence=0.93,
                    operator_attention=0.95,
                    latency_budget_seconds=60.0,
                    defense_layers_up=3,
                    defense_layers_required=3,
                    comms_health=0.98,
                ),
                expected_state=GateState.GREEN,
            ),
        ],
    )


def scenario_mq9_operator_distracted() -> Scenario:
    """MQ-9 strike where operator attention degrades — should trigger YELLOW."""
    return Scenario(
        name="mq9_operator_distracted",
        description=(
            "MQ-9 Reaper engagement window where operator attention has "
            "dropped to ~30% (operator handling parallel mission). H_required "
            "exceeds H_available but latency budget allows YELLOW prompt."
        ),
        steps=[
            ScenarioStep(
                label="t+0  operator distracted, latency budget intact",
                request=EngagementRequest(
                    timestamp=time.time(),
                    request_id="mq9-002",
                    elements=MQ9_REAPER.elements,
                    weights=MQ9_REAPER.weights,
                    transparency=MQ9_REAPER.transparency,
                    perception_confidence=0.85,
                    operator_attention=0.30,
                    latency_budget_seconds=45.0,
                    defense_layers_up=3,
                    defense_layers_required=3,
                    comms_health=0.95,
                ),
                expected_state=GateState.YELLOW,
            ),
        ],
    )


def scenario_kargu_short_window_no_operator() -> Scenario:
    """Kargu-2 black box, no operator, short terminal-phase window -> RED."""
    return Scenario(
        name="kargu_short_window_no_operator",
        description=(
            "Kargu-2 loitering munition in terminal phase. Black-box system "
            "means in-flight oversight infeasible regardless of operator. "
            "Short latency budget (2.5s) precludes YELLOW. Expected: RED."
        ),
        steps=[
            ScenarioStep(
                label="t+0  terminal-phase engagement, no operator-in-loop",
                request=EngagementRequest(
                    timestamp=time.time(),
                    request_id="kargu-001",
                    elements=KARGU_2.elements,
                    weights=KARGU_2.weights,
                    transparency=KARGU_2.transparency,
                    perception_confidence=0.78,
                    operator_attention=0.0,
                    latency_budget_seconds=2.5,
                    defense_layers_up=2,
                    defense_layers_required=2,
                    comms_health=0.95,
                ),
                expected_state=GateState.RED,
            ),
        ],
    )


def scenario_phalanx_geofence_violation() -> Scenario:
    """Phalanx defensive system, geofence-violating proposed engagement -> BLACK."""
    return Scenario(
        name="phalanx_geofence_violation",
        description=(
            "Phalanx CIWS proposed engagement against contact that would "
            "violate active geofence (e.g. friendly aircraft inside exclusion "
            "zone). Geofence breach forces immediate BLACK + kill-switch."
        ),
        steps=[
            ScenarioStep(
                label="t+0  geofence-violating proposed engagement",
                request=EngagementRequest(
                    timestamp=time.time(),
                    request_id="phalanx-001",
                    elements=PHALANX.elements,
                    weights=PHALANX.weights,
                    transparency=PHALANX.transparency,
                    perception_confidence=0.99,
                    operator_attention=1.0,
                    latency_budget_seconds=0.05,
                    defense_layers_up=3,
                    defense_layers_required=3,
                    comms_health=1.0,
                    geofence_compliant=False,
                ),
                expected_state=GateState.BLACK,
            ),
        ],
    )


def scenario_confidence_collapse() -> Scenario:
    """Perception confidence below floor -> BLACK regardless of other state."""
    return Scenario(
        name="confidence_collapse",
        description=(
            "MQ-9 engagement where perception confidence has collapsed to "
            "0.15 (sensor degradation, weather, jamming). Below 0.30 "
            "confidence floor forces BLACK regardless of operator/comms."
        ),
        steps=[
            ScenarioStep(
                label="t+0  perception confidence below floor",
                request=EngagementRequest(
                    timestamp=time.time(),
                    request_id="mq9-confidence-001",
                    elements=MQ9_REAPER.elements,
                    weights=MQ9_REAPER.weights,
                    transparency=MQ9_REAPER.transparency,
                    perception_confidence=0.15,
                    operator_attention=1.0,
                    latency_budget_seconds=120.0,
                    defense_layers_up=3,
                    defense_layers_required=3,
                    comms_health=1.0,
                ),
                expected_state=GateState.BLACK,
            ),
        ],
    )


ALL_SCENARIOS: dict[str, callable] = {
    "mq9_clean_engagement": scenario_mq9_clean_engagement,
    "mq9_operator_distracted": scenario_mq9_operator_distracted,
    "kargu_short_window_no_operator": scenario_kargu_short_window_no_operator,
    "phalanx_geofence_violation": scenario_phalanx_geofence_violation,
    "confidence_collapse": scenario_confidence_collapse,
}


def run_scenario(name: str) -> tuple[Kernel, AuditLog, Scenario, list]:
    """Run a single named scenario. Returns (kernel, log, scenario, decisions)."""
    if name not in ALL_SCENARIOS:
        raise KeyError(f"unknown scenario '{name}'. Available: {list(ALL_SCENARIOS)}")
    scenario = ALL_SCENARIOS[name]()
    kernel = Kernel()
    log = AuditLog()
    decisions = []
    for step in scenario.steps:
        decision = kernel.evaluate(step.request)
        log.record(decision)
        decisions.append(decision)
    return kernel, log, scenario, decisions


def list_scenarios() -> list[str]:
    return list(ALL_SCENARIOS.keys())
