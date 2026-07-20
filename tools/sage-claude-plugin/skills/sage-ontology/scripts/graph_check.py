#!/usr/bin/env python3
"""
In-memory graph validator for ontology entities and relations.

Reads JSON from stdin, validates structural constraints, prints results.
Zero dependencies beyond Python stdlib. Zero file I/O.

Input format:
    {
      "entities": [{"id": "...", "type": "...", "properties": {...}}, ...],
      "relations": [{"from_id": "...", "from_type": "...", "rel": "...", "to_id": "...", "to_type": "..."}, ...]
    }

Usage:
    echo '{"entities":[...],"relations":[...]}' | python3 graph_check.py
    echo '...' | python3 graph_check.py --check cycles
    echo '...' | python3 graph_check.py --check all

Output: {"valid": bool, "errors": [...], "warnings": [...]}
Exit:   0 = valid, 1 = errors, 2 = bad input
"""

import json
import sys
from collections import defaultdict
from datetime import datetime

# ── Schema (minimal core — extend via [Schema:*] entries) ────────────

REQUIRED = {
    "Task":     ("title", "status"),
    "Person":   ("name",),
    "Project":  ("name",),
    "Event":    ("title", "start"),
    "Document": ("title",),
    "Goal":     ("description",),
    "Note":     ("content",),
}

ENUMS = {
    ("Task",    "status"):   frozenset(("open", "in_progress", "blocked", "done", "cancelled")),
    ("Task",    "priority"): frozenset(("low", "medium", "high", "urgent")),
    ("Project", "status"):   frozenset(("planning", "active", "paused", "completed", "archived")),
}

FORBIDDEN = {
    "Credential": frozenset(("password", "secret", "token", "key", "api_key")),
}

RELATION_SPEC = {
    #  rel_type:     (from_types,                     to_types,                              cardinality,  acyclic)
    "has_owner":     (("Project", "Task"),             ("Person",),                           "many_to_one",  False),
    "has_task":      (("Project",),                    ("Task",),                             "one_to_many",  False),
    "assigned_to":   (("Task",),                       ("Person",),                           "many_to_one",  False),
    "blocks":        (("Task",),                       ("Task",),                             "many_to_many", True),
    "part_of":       (("Task", "Document", "Event"),   ("Project",),                          "many_to_one",  False),
    "depends_on":    (("Task", "Project"),              ("Task", "Project", "Event"),           "many_to_many", True),
    "member_of":     (("Person",),                     ("Organization",),                     "many_to_many", False),
    "has_goal":      (("Project",),                    ("Goal",),                             "one_to_many",  False),
    "mentions":      (("Document", "Message", "Note"), ("Person", "Project", "Task", "Event"), "many_to_many", False),
    "follows_up":    (("Task", "Event"),               ("Event", "Message"),                   "many_to_one",  False),
    "attendee_of":   (("Person",),                     ("Event",),                            "many_to_many", False),
}


# ── Validators ───────────────────────────────────────────────────────

def check_required(entities, _relations):
    errors = []
    for e in entities:
        eid, etype = e["id"], e["type"]
        props = e.get("properties", {})
        for field in REQUIRED.get(etype, ()):
            val = props.get(field)
            if val is None or val == "":
                errors.append(f"{eid}: missing required '{field}' for {etype}")
    return errors


def check_enums(entities, _relations):
    errors = []
    for e in entities:
        eid, etype = e["id"], e["type"]
        props = e.get("properties", {})
        for field, val in props.items():
            allowed = ENUMS.get((etype, field))
            if allowed is not None and val is not None and val not in allowed:
                errors.append(f"{eid}: {field}='{val}' not in {sorted(allowed)}")
    return errors


def check_forbidden(entities, _relations):
    errors = []
    for e in entities:
        eid, etype = e["id"], e["type"]
        bad = FORBIDDEN.get(etype)
        if bad:
            for field in bad & e.get("properties", {}).keys():
                errors.append(f"{eid}: forbidden property '{field}' — use secret_ref")
    return errors


def check_event_times(entities, _relations):
    errors = []
    for e in entities:
        if e["type"] != "Event":
            continue
        props = e.get("properties", {})
        start, end = props.get("start"), props.get("end")
        if start and end:
            try:
                if datetime.fromisoformat(str(end)) < datetime.fromisoformat(str(start)):
                    errors.append(f"{e['id']}: end < start")
            except (ValueError, TypeError):
                errors.append(f"{e['id']}: invalid datetime in start/end")
    return errors


def check_cycles(_entities, relations):
    """
    Detect cycles in acyclic relation types.
    Iterative DFS with iterator-per-node: mirrors recursion exactly,
    O(V + E) time, O(V) memory, zero list copying.
    """
    errors = []

    acyclic_types = {rel for rel, spec in RELATION_SPEC.items() if spec[3]}

    for rel_type in acyclic_types:
        adj = defaultdict(list)
        nodes = set()
        for r in relations:
            if r["rel"] == rel_type:
                adj[r["from_id"]].append(r["to_id"])
                nodes.add(r["from_id"])
                nodes.add(r["to_id"])

        if not nodes:
            continue

        visited = set()
        on_stack = set()
        cycle_found = None

        for start in nodes:
            if start in visited:
                continue

            # Stack of (node, neighbor_iterator) — exact recursion mirror
            stack = [(start, iter(adj.get(start, ())))]
            visited.add(start)
            on_stack.add(start)

            while stack:
                node, neighbors = stack[-1]
                try:
                    nxt = next(neighbors)
                    if nxt in on_stack:
                        # Cycle: path is the stack from nxt to current + nxt
                        path = [n for n, _ in stack]
                        idx = path.index(nxt)
                        cycle_found = path[idx:] + [nxt]
                        break
                    if nxt not in visited:
                        visited.add(nxt)
                        on_stack.add(nxt)
                        stack.append((nxt, iter(adj.get(nxt, ()))))
                except StopIteration:
                    stack.pop()
                    on_stack.discard(node)

            if cycle_found:
                break

        if cycle_found:
            errors.append(f"cycle in '{rel_type}': {' → '.join(cycle_found)}")

    return errors


def check_cardinality(_entities, relations):
    errors = []

    # Count outgoing per (source, rel_type) and incoming per (target, rel_type)
    out_count = defaultdict(int)
    in_count = defaultdict(int)

    for r in relations:
        rel = r["rel"]
        out_count[(r["from_id"], rel)] += 1
        in_count[(r["to_id"], rel)] += 1

    for (eid, rel), count in out_count.items():
        spec = RELATION_SPEC.get(rel)
        if spec and spec[2] == "many_to_one" and count > 1:
            errors.append(f"{eid}: {count} outgoing '{rel}' (many_to_one allows 1)")

    for (tid, rel), count in in_count.items():
        spec = RELATION_SPEC.get(rel)
        if spec and spec[2] == "one_to_many" and count > 1:
            errors.append(f"{tid}: {count} incoming '{rel}' from different sources")

    return errors


def check_relation_types(entities, relations):
    warnings = []
    type_map = {e["id"]: e["type"] for e in entities}

    for r in relations:
        spec = RELATION_SPEC.get(r["rel"])
        if not spec:
            continue

        from_types, to_types = spec[0], spec[1]
        ft = r.get("from_type") or type_map.get(r["from_id"])
        tt = r.get("to_type") or type_map.get(r["to_id"])

        if ft and ft not in from_types:
            warnings.append(f"'{r['rel']}' from {r['from_id']}: type '{ft}' not in {list(from_types)}")
        if tt and tt not in to_types:
            warnings.append(f"'{r['rel']}' to {r['to_id']}: type '{tt}' not in {list(to_types)}")

    return warnings


# ── Dispatch ─────────────────────────────────────────────────────────

CHECKS = {
    "required":       check_required,
    "enums":          check_enums,
    "forbidden":      check_forbidden,
    "event_times":    check_event_times,
    "cycles":         check_cycles,
    "cardinality":    check_cardinality,
    "relation_types": check_relation_types,
}

WARNING_CHECKS = {"relation_types"}


def validate(entities, relations, checks=None):
    """Run validation checks. Returns (errors, warnings) lists."""
    run = list(CHECKS) if checks is None else checks
    errors, warnings = [], []
    for name in run:
        results = CHECKS[name](entities, relations)
        (warnings if name in WARNING_CHECKS else errors).extend(results)
    return errors, warnings


def main():
    check = "all"
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--check" and i < len(sys.argv) - 1:
            check = sys.argv[i + 1]

    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        json.dump({"valid": False, "errors": [f"bad input: {e}"], "warnings": []}, sys.stdout, indent=2)
        sys.exit(2)

    if isinstance(data, list):
        entities, relations = data, []
    else:
        entities = data.get("entities", [])
        relations = data.get("relations", [])

    checks = None if check == "all" else [check]
    errors, warnings = validate(entities, relations, checks)

    json.dump({
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checked": len(entities),
    }, sys.stdout, indent=2)
    print()
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
