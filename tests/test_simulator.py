"""
Tests for the engagement-scenario simulator.

Verifies that each canonical scenario produces the expected gate state
end-to-end through the kernel + audit log + chain verification.
"""

from chof_kernel.simulator import ALL_SCENARIOS, list_scenarios, run_scenario


def test_all_scenarios_registered():
    expected = {
        "mq9_clean_engagement",
        "mq9_operator_distracted",
        "kargu_short_window_no_operator",
        "phalanx_geofence_violation",
        "confidence_collapse",
    }
    assert set(list_scenarios()) == expected


def test_mq9_clean_engagement_is_green():
    _, log, scenario, decisions = run_scenario("mq9_clean_engagement")
    for step, dec in zip(scenario.steps, decisions):
        assert dec.state == step.expected_state, (
            f"step {step.label!r}: expected {step.expected_state.value} "
            f"got {dec.state.value}"
        )
    ok, _ = log.verify()
    assert ok


def test_mq9_operator_distracted_is_yellow():
    _, log, scenario, decisions = run_scenario("mq9_operator_distracted")
    for step, dec in zip(scenario.steps, decisions):
        assert dec.state == step.expected_state
    ok, _ = log.verify()
    assert ok


def test_kargu_short_window_is_red():
    _, log, scenario, decisions = run_scenario("kargu_short_window_no_operator")
    for step, dec in zip(scenario.steps, decisions):
        assert dec.state == step.expected_state
    ok, _ = log.verify()
    assert ok


def test_phalanx_geofence_violation_is_black():
    _, log, scenario, decisions = run_scenario("phalanx_geofence_violation")
    for step, dec in zip(scenario.steps, decisions):
        assert dec.state == step.expected_state
    ok, _ = log.verify()
    assert ok


def test_confidence_collapse_is_black():
    _, log, scenario, decisions = run_scenario("confidence_collapse")
    for step, dec in zip(scenario.steps, decisions):
        assert dec.state == step.expected_state
    ok, _ = log.verify()
    assert ok


def test_every_scenario_audit_chain_verifies():
    """Sanity sweep: every canonical scenario must produce a verifiable
    audit log chain."""
    for name in list_scenarios():
        _, log, _, _ = run_scenario(name)
        ok, reason = log.verify()
        assert ok, f"{name}: {reason}"
