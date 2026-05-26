"""
Tests for the CHOF-Kernel state machine.
"""

import time

import pytest

from chof_calc.systems import KARGU_2, MQ9_REAPER, PHALANX

from chof_kernel.kernel import (
    EngagementRequest,
    GateState,
    Kernel,
    KernelConfig,
)


def _baseline_mq9_request(**overrides):
    base = dict(
        timestamp=time.time(),
        request_id="test-001",
        elements=MQ9_REAPER.elements,
        weights=MQ9_REAPER.weights,
        transparency=MQ9_REAPER.transparency,
        perception_confidence=0.90,
        operator_attention=0.95,
        latency_budget_seconds=60.0,
        defense_layers_up=3,
        defense_layers_required=3,
        comms_health=0.98,
        geofence_compliant=True,
    )
    base.update(overrides)
    return EngagementRequest(**base)


def test_green_when_operator_fully_attentive_and_high_confidence():
    """Operator attention + clean comms covers H_required -> GREEN."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request())
    assert decision.state == GateState.GREEN
    assert decision.h_available >= decision.h_required


def test_yellow_when_operator_distracted_but_latency_intact():
    """Operator attention drops but latency budget allows YELLOW prompt."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        operator_attention=0.30,
        latency_budget_seconds=45.0,
    ))
    assert decision.state == GateState.YELLOW
    assert decision.h_required > decision.h_available


def test_red_when_latency_too_short_for_yellow():
    """Short latency budget precludes operator confirmation -> RED."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        operator_attention=0.20,
        latency_budget_seconds=2.0,
    ))
    assert decision.state == GateState.RED


def test_red_when_no_operator_and_required_exceeds_available():
    """No operator + H_required > H_available -> RED."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        operator_attention=0.0,
        latency_budget_seconds=60.0,
    ))
    assert decision.state == GateState.RED


def test_red_when_comms_degraded_below_floor():
    """Comms health below floor precludes operator confirmation -> RED."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        operator_attention=0.30,
        comms_health=0.30,
    ))
    assert decision.state == GateState.RED


def test_black_when_geofence_violated():
    """Geofence violation forces BLACK regardless of other state."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(geofence_compliant=False))
    assert decision.state == GateState.BLACK


def test_black_when_defense_layers_down():
    """Defense-in-depth shortage forces BLACK."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        defense_layers_up=1,
        defense_layers_required=3,
    ))
    assert decision.state == GateState.BLACK
    assert "defense_layers_down" in " ".join(decision.triggered_rules)


def test_black_when_confidence_collapses():
    """Perception confidence below floor forces BLACK."""
    kernel = Kernel()
    decision = kernel.evaluate(_baseline_mq9_request(
        perception_confidence=0.15,
    ))
    assert decision.state == GateState.BLACK
    assert "confidence_collapse" in " ".join(decision.triggered_rules)


def test_black_box_in_flight_supervision_cap():
    """Black-box systems have in-flight oversight CAPPED at 50% even when
    operator attention and comms are 100%. This is the H_v2 modality
    enforcement at the kernel level."""
    kernel = Kernel()
    # Use Kargu-2 (BLACK BOX) but with otherwise-perfect conditions.
    decision = kernel.evaluate(EngagementRequest(
        timestamp=time.time(),
        request_id="kargu-test",
        elements=KARGU_2.elements,
        weights=KARGU_2.weights,
        transparency=KARGU_2.transparency,
        perception_confidence=0.95,
        operator_attention=1.0,
        latency_budget_seconds=60.0,
        defense_layers_up=3,
        defense_layers_required=3,
        comms_health=1.0,
        geofence_compliant=True,
    ))
    # H_available was nominal 100% (1.0 * 1.0 * 100), capped to 50%.
    assert decision.h_available == 50.0


def test_invalid_inputs_raise():
    """Inputs outside their domains must raise ValueError."""
    with pytest.raises(ValueError, match="perception_confidence"):
        _baseline_mq9_request(perception_confidence=-0.1)
    with pytest.raises(ValueError, match="operator_attention"):
        _baseline_mq9_request(operator_attention=1.5)
    with pytest.raises(ValueError, match="comms_health"):
        _baseline_mq9_request(comms_health=2.0)
    with pytest.raises(ValueError, match="latency_budget_seconds"):
        _baseline_mq9_request(latency_budget_seconds=0)


def test_kernel_decision_is_deterministic():
    """Same request produces same decision; the kernel is a pure function."""
    kernel = Kernel()
    req = _baseline_mq9_request()
    d1 = kernel.evaluate(req)
    d2 = kernel.evaluate(req)
    assert d1.state == d2.state
    assert abs(d1.h_required - d2.h_required) < 1e-9
    assert abs(d1.h_available - d2.h_available) < 1e-9


def test_configurable_thresholds():
    """KernelConfig thresholds (confidence floor etc) are respected."""
    kernel = Kernel(KernelConfig(confidence_floor=0.50))
    # Confidence 0.40 — under custom floor 0.50, should BLACK.
    decision = kernel.evaluate(_baseline_mq9_request(perception_confidence=0.40))
    assert decision.state == GateState.BLACK
