#!/usr/bin/env python3
"""
check-workflows.py — the CI workflow files are valid YAML and well-formed.

Nothing in this repo ever parsed .github/workflows/*.yml, so release.yml sat
broken for the whole Phase 1–3 program without anyone noticing: its publish step
embedded a Python heredoc whose body starts at column 0, and a non-indented line
closes the enclosing `run: |` block scalar. GitHub would have rejected the file
outright — but release.yml only fires on a tag push, and no tag was ever pushed.
The bug was scheduled to surface exactly once: at `git tag v1.2.0`.

A workflow that cannot be parsed does not run, and a workflow that does not run
is a gate that silently is not there. That is the failure mode Sage exists to
prevent, so it gets a check of its own.

Catches:
  - invalid YAML (the heredoc trap above, bad indentation, tabs)
  - a workflow with no `jobs:`, or a job with no `steps:`
  - a step that is neither `run:` nor `uses:` (does nothing)
  - an empty `run:` body

Usage:  python3 develop/validators/check-workflows.py [--repo-root PATH]
Exit:   0 = all valid | 1 = a workflow is broken | 2 = PyYAML unavailable

Python 3.8+. Needs PyYAML (`pip install pyyaml`) — the one validator here that
is not stdlib-only, because writing a YAML parser to check YAML is not the job.
Exit 2 (unverifiable) is distinct from exit 1 (broken), per the gate contract:
a missing parser must never read as a pass.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("⚠️  UNVERIFIABLE — PyYAML is not installed, so the workflow files "
          "were not parsed.", file=sys.stderr)
    print("    pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def check_workflow(path: pathlib.Path) -> list:
    """Return a list of problems with one workflow file."""
    problems = []
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        # The message carries the line/column, which is the whole value here.
        detail = " ".join(str(exc).split())
        return [f"invalid YAML — {detail}"]

    if not isinstance(doc, dict):
        return ["not a YAML mapping"]

    jobs = doc.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return ["no jobs defined"]

    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            problems.append(f"job {job_name}: not a mapping")
            continue
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"job {job_name}: no steps")
            continue
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                problems.append(f"job {job_name} step {i}: not a mapping")
                continue
            label = step.get("name") or step.get("uses") or f"step {i}"
            has_run, has_uses = "run" in step, "uses" in step
            if not has_run and not has_uses:
                problems.append(f"job {job_name}: {label!r} has neither run: nor uses:")
            if has_run and not str(step["run"]).strip():
                problems.append(f"job {job_name}: {label!r} has an empty run: body")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--repo-root", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[2])
    args = parser.parse_args()

    workflows = sorted((args.repo_root / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        print("✗ no workflow files found — is --repo-root right?")
        return 1

    broken = 0
    for wf in workflows:
        problems = check_workflow(wf)
        if problems:
            broken += 1
            print(f"✗ {wf.relative_to(args.repo_root)}")
            for p in problems:
                print(f"    {p}")

    if broken:
        print()
        print(f"FAIL — {broken} of {len(workflows)} workflow file(s) are broken.")
        print("  A workflow that does not parse does not run, and a gate that")
        print("  does not run is not a gate.")
        return 1

    print()
    print(f"OK — {len(workflows)} workflow file(s) parse and are well-formed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
