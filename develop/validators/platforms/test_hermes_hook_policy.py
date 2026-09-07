#!/usr/bin/env python3
"""Behavioral contract for Task 14: exact 7+4 hook policy, consent, failure,
and restart semantics (spec 5.3.6-14).

The policy module under test is
``runtime/platforms/community/hermes/setup/hook_config.py``. These tests pin
the failure matrix BEFORE the implementation exists (red-first): the exact
seven-blocking/four-observer registry, the consent rule (never profile-wide
hooks_auto_accept), candidate YAML validation, the post-restart veto matrix,
and restore-on-failed-activation.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
SETUP = ROOT / "runtime" / "platforms" / "community" / "hermes" / "setup"
sys.path.insert(0, str(SETUP))

import hook_config  # red: module does not exist yet — collection error is the RED


# ── Registry shape (spec 5.3.6-7) ────────────────────────────────────────────

def test_registry_is_exactly_seven_blocking_and_four_observers() -> None:
    registry = hook_config.expected_registry()
    pre = [entry for entry in registry if entry["event"] == "pre_tool_call"]
    post = [entry for entry in registry if entry["event"] == "post_tool_call"]
    session = [entry for entry in registry if entry["event"] == "on_session_start"]
    assert len(pre) == 7
    assert len(post) == 4
    assert session == [
        {
            "event": "on_session_start",
            "matcher": None,
            "script": "sage-session-init.sh",
            "fail_closed": False,
        }
    ]
    assert all(entry["fail_closed"] is True for entry in pre)
    assert all(entry["fail_closed"] is False for entry in post)


def test_registry_names_the_sanctioned_scripts() -> None:
    registry = hook_config.expected_registry()
    pre_scripts = {
        entry["script"] for entry in registry if entry["event"] == "pre_tool_call"
    }
    assert pre_scripts == {
        "sage-spec-gate.sh",
        "sage-tdd-gate.sh",
        "sage-bookkeeping-gate.sh",
        "sage-secrets-gate.sh",
        "sage-verify-gate.sh",
        "sage-config-gate.sh",
        "sage-scope-gate.sh",
    }
    post_scripts = {
        entry["script"] for entry in registry if entry["event"] == "post_tool_call"
    }
    assert post_scripts == {
        "sage-verify-tracker.sh",
        "sage-degradation-log.sh",
        "sage-manifest-sync.sh",
        "sage-scope-journal.sh",
    }


# ── Candidate validation (spec 5.3.7, 5.3.12) ───────────────────────────────

VALID_YAML = """hooks:
  on_session_start:
    - command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-session-init.sh\\""
      fail_closed: false
      timeout: 30
  pre_tool_call:
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-spec-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-tdd-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-bookkeeping-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-secrets-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: terminal
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-verify-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: write_file|patch|terminal
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-config-gate.sh"
      fail_closed: true
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-scope-gate.sh"
      fail_closed: true
      timeout: 30
  post_tool_call:
    - matcher: write_file|patch|terminal
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-verify-tracker.sh"
      fail_closed: false
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-degradation-log.sh"
      fail_closed: false
      timeout: 30
    - matcher: write_file|patch
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-manifest-sync.sh"
      fail_closed: false
      timeout: 30
    - matcher: write_file|patch|terminal
      command: "C:/Program Files/Git/bin/bash.exe \\"G:/profile/hooks/sage-hermes-gate.sh\\" sage-scope-journal.sh"
      fail_closed: false
      timeout: 30
"""


def test_valid_candidate_passes_with_exact_counts() -> None:
    result = hook_config.validate_candidate_config(VALID_YAML)
    assert result["ok"] is True
    assert result["blocking_count"] == 7
    assert result["observer_count"] == 4
    assert result["lifecycle_count"] == 1
    assert result["errors"] == []


def test_hooks_auto_accept_is_never_accepted() -> None:
    result = hook_config.validate_candidate_config(
        VALID_YAML + "hooks_auto_accept: true\n"
    )
    assert result["ok"] is False
    assert any("hooks_auto_accept" in error for error in result["errors"])


def test_unclassified_parity_change_fails() -> None:
    extra = (
        "    - matcher: terminal\n"
        "      command: \"bash \\\\\"G:/profile/hooks/sage-hermes-gate.sh\\\\\" sage-extra.sh\"\n"
        "      fail_closed: true\n"
        "      timeout: 30\n"
    )
    mutated = VALID_YAML.replace("  post_tool_call:\n", extra + "  post_tool_call:\n")
    result = hook_config.validate_candidate_config(mutated)
    assert result["ok"] is False
    assert result["blocking_count"] != 7 or result["errors"]


def test_missing_blocking_entry_fails() -> None:
    mutated = "\n".join(
        line for line in VALID_YAML.splitlines() if "sage-scope-gate.sh" not in line
    ) + "\n"
    result = hook_config.validate_candidate_config(mutated)
    assert result["ok"] is False


def test_malformed_yaml_fails_closed() -> None:
    result = hook_config.validate_candidate_config("hooks:\n  pre_tool_call: [unclosed\n")
    assert result["ok"] is False
    assert result["errors"]


def test_matcher_drift_fails() -> None:
    lines = VALID_YAML.splitlines()
    for index, line in enumerate(lines):
        if "sage-verify-tracker.sh" in line:
            assert "write_file|patch|terminal" in lines[index - 1]
            lines[index - 1] = lines[index - 1].replace(
                "write_file|patch|terminal", "write_file|patch"
            )
            break
    result = hook_config.validate_candidate_config("\n".join(lines) + "\n")
    assert result["ok"] is False
    assert any("matcher drift" in error for error in result["errors"])


def test_adapter_entry_without_gate_script_fails() -> None:
    orphan = (
        "    - matcher: terminal\n"
        "      command: \"C:/Program Files/Git/bin/bash.exe \\\\\\\"G:/profile/hooks/sage-hermes-gate.sh\\\\\\\"\"\n"
        "      fail_closed: true\n"
        "      timeout: 30\n"
    )
    mutated = VALID_YAML.replace("  post_tool_call:\n", orphan + "  post_tool_call:\n")
    result = hook_config.validate_candidate_config(mutated)
    assert result["ok"] is False
    assert any("exactly one gate script" in error for error in result["errors"])


def test_unrecognized_decision_vetoes_blocking_hook() -> None:
    outcome = hook_config.classify_hook_result(
        returncode=0,
        stdout='{"decision": "maybe"}',
        stderr="",
        timed_out=False,
        fail_closed=True,
    )
    assert outcome == "block"


# ── Failure matrix classification (spec 5.3.13-14) ───────────────────────────

@pytest.mark.parametrize(
    "returncode,stdout,timed_out,expected",
    [
        (0, '{"decision": "allow"}', False, "allow"),
        (2, "", False, "block"),
        (0, '{"decision": "block", "reason": "x"}', False, "block"),
        (None, "", True, "block"),  # timeout vetoes a blocking hook
        (1, "", False, "block"),  # crash vetoes a blocking hook
        (0, "not json at all", False, "block"),  # malformed nonempty output vetoes
        (None, "", False, "block"),  # missing executable vetoes
    ],
)
def test_blocking_hook_failures_veto(returncode, stdout, timed_out, expected) -> None:
    outcome = hook_config.classify_hook_result(
        returncode=returncode,
        stdout=stdout,
        stderr="",
        timed_out=timed_out,
        fail_closed=True,
    )
    assert outcome == expected


@pytest.mark.parametrize(
    "returncode,stdout,timed_out",
    [
        (None, "", True),  # timeout
        (1, "", False),  # crash
        (0, "not json at all", False),  # malformed
        (None, "", False),  # missing executable
    ],
)
def test_observer_failures_stay_visible_but_never_block(returncode, stdout, timed_out) -> None:
    outcome = hook_config.classify_hook_result(
        returncode=returncode,
        stdout=stdout,
        stderr="",
        timed_out=timed_out,
        fail_closed=False,
    )
    assert outcome != "block"


# ── Activation / restore (spec 5.3.12-13) ────────────────────────────────────

def test_activation_with_missing_consent_restores_prior_config() -> None:
    prior = "hooks:\n  pre_tool_call: []\n"
    plan = hook_config.plan_activation(
        current_config=prior,
        candidate_config=VALID_YAML,
        consent_granted=False,
    )
    assert plan["apply"] is False
    assert plan["restore_config"] == prior
    assert plan["errors"]


def test_activation_with_malformed_candidate_restores_prior_config() -> None:
    prior = "hooks:\n  pre_tool_call: []\n"
    plan = hook_config.plan_activation(
        current_config=prior,
        candidate_config="hooks: [unclosed\n",
        consent_granted=True,
    )
    assert plan["apply"] is False
    assert plan["restore_config"] == prior


def test_activation_with_valid_candidate_and_consent_applies() -> None:
    prior = "hooks:\n  pre_tool_call: []\n"
    plan = hook_config.plan_activation(
        current_config=prior,
        candidate_config=VALID_YAML,
        consent_granted=True,
    )
    assert plan["apply"] is True
    assert plan["restore_config"] == prior
    assert plan["candidate_config"] == VALID_YAML
