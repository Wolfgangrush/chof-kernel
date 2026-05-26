"""
Command-line interface for chof-kernel reference implementation.

Usage:
    chof-kernel scenarios             # list available scenarios
    chof-kernel run <scenario>        # run one scenario, show decision chain
    chof-kernel run-all               # run all scenarios, verify audit chains
    chof-kernel version
"""

from __future__ import annotations

import argparse
import sys

from chof_kernel import __version__
from chof_kernel.simulator import (
    ALL_SCENARIOS,
    list_scenarios,
    run_scenario,
)


def _banner() -> str:
    return (
        "==============================================================\n"
        "  CHOF-KERNEL v" + __version__ + " (Python reference implementation)\n"
        "  Embedded human-oversight kernel for autonomous systems\n"
        "  Tactical safety governor -- pattern: TCAS + AEB\n"
        "  Production target: C++/Rust port for ROS2/PX4/ArduPilot\n"
        "=============================================================="
    )


def _state_emoji(state: str) -> str:
    return {
        "green": "[GREEN]   ",
        "yellow": "[YELLOW]  ",
        "red": "[RED]     ",
        "black": "[BLACK]   ",
    }.get(state, state)


def cmd_scenarios(args: argparse.Namespace) -> int:
    print(_banner())
    print()
    print("Available engagement scenarios:")
    print()
    for name in list_scenarios():
        scenario = ALL_SCENARIOS[name]()
        print(f"  * {name}")
        # word-wrap description at ~70 chars
        words = scenario.description.split()
        line = "    "
        for w in words:
            if len(line) + len(w) > 72:
                print(line)
                line = "    "
            line += w + " "
        if line.strip():
            print(line.rstrip())
        print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    print(_banner())
    print()
    try:
        kernel, log, scenario, decisions = run_scenario(args.scenario)
    except KeyError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(f"SCENARIO: {scenario.name}")
    print(f"  {scenario.description}")
    print()

    for step, decision in zip(scenario.steps, decisions):
        print(f"STEP: {step.label}")
        print(f"  Expected: {step.expected_state.value:8}  "
              f"Actual: {_state_emoji(decision.state.value)}")
        print(f"  H_required:  {decision.h_required:.2f} %")
        print(f"  H_available: {decision.h_available:.2f} %")
        print(f"  Reasoning:")
        words = decision.reasoning.split()
        line = "    "
        for w in words:
            if len(line) + len(w) > 72:
                print(line)
                line = "    "
            line += w + " "
        if line.strip():
            print(line.rstrip())
        if decision.triggered_rules:
            print(f"  Rules fired:")
            for rule in decision.triggered_rules:
                print(f"    - {rule}")
        match = "PASS" if decision.state == step.expected_state else "FAIL"
        print(f"  Match: {match}")
        print()

    # Verify audit log chain
    ok, reason = log.verify()
    print("AUDIT-LOG VERIFICATION")
    print(f"  Public key (Ed25519): {log.public_key_hex}")
    print(f"  Entries: {len(log.entries)}")
    print(f"  Chain verification: {'PASS  ' if ok else 'FAIL  '} {reason}")
    print()

    if args.export:
        log.export_json(args.export)
        print(f"Audit log exported to: {args.export}")
    return 0


def cmd_run_all(args: argparse.Namespace) -> int:
    print(_banner())
    print()
    print(f"Running all {len(ALL_SCENARIOS)} scenarios...")
    print()
    pass_count = 0
    fail_count = 0
    for name in list_scenarios():
        kernel, log, scenario, decisions = run_scenario(name)
        for step, decision in zip(scenario.steps, decisions):
            match = decision.state == step.expected_state
            label = "PASS" if match else "FAIL"
            print(
                f"  {label}  {name:<40} expected={step.expected_state.value:8} "
                f"actual={decision.state.value:8} "
                f"H_req={decision.h_required:5.1f} H_avail={decision.h_available:5.1f}"
            )
            if match:
                pass_count += 1
            else:
                fail_count += 1
        # Verify each scenario's audit log
        ok, _ = log.verify()
        chain_label = "PASS" if ok else "FAIL"
        print(f"        audit-chain: {chain_label}")
        print()
    print(
        f"SUMMARY: {pass_count} steps PASS, {fail_count} steps FAIL "
        f"across {len(ALL_SCENARIOS)} scenarios."
    )
    return 0 if fail_count == 0 else 1


def cmd_version(args: argparse.Namespace) -> int:
    print(f"chof-kernel {__version__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chof-kernel",
        description=(
            "Embedded human-oversight kernel for autonomous systems "
            "(Python reference implementation)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scen = sub.add_parser("scenarios", help="List available engagement scenarios")
    p_scen.set_defaults(func=cmd_scenarios)

    p_run = sub.add_parser("run", help="Run a single named scenario")
    p_run.add_argument("scenario", help="Scenario name (see `chof-kernel scenarios`)")
    p_run.add_argument(
        "--export",
        help="Optional path to export the audit log as JSON for verification",
    )
    p_run.set_defaults(func=cmd_run)

    p_all = sub.add_parser(
        "run-all", help="Run every scenario and report pass/fail summary"
    )
    p_all.set_defaults(func=cmd_run_all)

    p_ver = sub.add_parser("version", help="Print version and exit")
    p_ver.set_defaults(func=cmd_version)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
