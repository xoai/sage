#!/usr/bin/env python3
"""contract.py — the platform capability contract, and the tier derived from it.

Before v1.3.0, `platform.yaml` declared capabilities that nothing read and
nothing checked. `claude-code/platform.yaml` claimed `supported-os: [linux,
macos, windows]`; nothing has ever tested Windows. It said `tier: 1`, by hand,
because someone typed a 1.

That is the same shape of failure this whole program exists to correct: a claim
with no mechanism behind it. The README's enforcement truth table was
hand-written prose about which platforms enforce what — which is exactly the kind
of prose the v1.2.1 eval kept catching in a lie.

So:

  * The vocabulary is the one that decides ENFORCEMENT, not the one that reads
    nicely in a feature matrix. `pre-tool-veto` — can this platform BLOCK a tool
    call with a reason the model sees? — is the single most consequential fact
    about a platform, and the old schema had no word for it.

  * Tier is DERIVED, never declared. A tier you can type is a tier you can be
    wrong about. Here it is a function of the capabilities, and if you want a
    better tier you have to acquire a capability.

  * `attested` is a real value, and it costs something: an evidence file with a
    transcript and an expiry (C15). It is the honest middle between "true"
    (which we can check automatically) and "false" (which throws away a real
    capability because CI cannot reach it). What it is NOT is a way to write
    `true` without doing the work — an expired attestation fails conformance.

Python 3.8+, stdlib only.

Usage:
    contract.py --check              # every contract parses; tiers derive; no legacy mismatches
    contract.py --show <platform>    # one contract, resolved, with its derived tier
    contract.py --json               # machine-readable, for gen_truth_table.py
"""

import argparse
import datetime
import json
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLATFORMS = REPO_ROOT / "runtime" / "platforms"
CONTRACT_VERSION = 2

# ── The capabilities that decide what Sage can enforce ───────────────────────
#
# Each of these maps to something Sage does or cannot do. They are not features;
# they are the preconditions of enforcement.
CAPABILITIES = {
    "context-injection":
        "deliver the eager core at session start",
    "command-delivery":
        "slash-commands, or an equivalent explicit invocation",
    "native-skill-discovery":
        "description-triggered on-demand skills (ADR-9 delivery class 2)",
    "pre-tool-veto":
        "BLOCK a tool call, with a reason the model can act on",
    "post-tool-events":
        "observe completed tool calls (the audit hooks)",
    "subagent-dispatch":
        "fresh-context task delegation (ADR-10)",
    "session-events":
        "start/stop lifecycle for state management",
}

VALID_VALUES = (True, False, "attested")


class ContractError(Exception):
    pass


# ── A small YAML reader (see check-eval-coverage.py for why not PyYAML) ──────

def _scalar(v):
    v = v.strip()
    # Strip a trailing comment. The capability lines carry them, and they are the
    # most useful prose in the file — `pre-tool-veto: attested  # ...including
    # inside subagents` is the reason the value is what it is. A reader that
    # cannot handle them would force the contract to be written without them,
    # which is optimising the file for the parser instead of for the person.
    if "#" in v:
        quoted = v.startswith(('"', "'"))
        if not quoted:
            v = v.split("#", 1)[0].strip()
    v = v.strip().strip('"').strip("'")
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v.startswith("[") and v.endswith("]"):
        return [x.strip().strip('"').strip("'")
                for x in v[1:-1].split(",") if x.strip()]
    return v


def parse_contract(text):
    """platform.yaml → dict. Handles the document markers, nested maps, and the
    `attestations:` list of maps. Anything more exotic is not schema and is a bug
    in the contract, not in this reader."""
    doc = {}
    stack = [(0, doc)]
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue

        indent = len(raw) - len(raw.lstrip())

        # A list item under the current key (attestations, supported-os, …)
        if stripped.startswith("- "):
            while stack and stack[-1][0] >= indent + 1 and len(stack) > 1:
                stack.pop()
            parent = stack[-1][1]
            key = parent.get("__last__")
            if key is None:
                raise ContractError("list item with no parent key: %r" % stripped)
            target = parent.setdefault(key, [])
            if not isinstance(target, list):
                target = parent[key] = []
            body = stripped[2:].strip()
            if ":" in body:
                item = {}
                k, _, v = body.partition(":")
                item[k.strip()] = _scalar(v)
                # subsequent more-indented lines belong to this item
                while i < len(lines):
                    nxt = lines[i]
                    if not nxt.strip() or nxt.strip().startswith("#"):
                        i += 1
                        continue
                    nind = len(nxt) - len(nxt.lstrip())
                    if nind <= indent or nxt.strip().startswith("- "):
                        break
                    k2, _, v2 = nxt.strip().partition(":")
                    item[k2.strip()] = _scalar(v2)
                    i += 1
                target.append(item)
            else:
                target.append(_scalar(body))
            continue

        if ":" not in stripped:
            raise ContractError("not a key: %r" % stripped)

        key, _, value = stripped.partition(":")
        key, value = key.strip(), value.strip()

        while len(stack) > 1 and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]

        # Folded/blank value → this key owns a nested block or a list
        if value in ("", ">", "|"):
            if value in (">", "|"):
                block = []
                while i < len(lines):
                    nxt = lines[i]
                    nind = len(nxt) - len(nxt.lstrip())
                    if nxt.strip() and nind <= indent:
                        break
                    block.append(nxt.strip())
                    i += 1
                parent[key] = " ".join(b for b in block if b)
                parent["__last__"] = key
                continue
            # A key with no value owns either a nested MAP or a LIST, and which
            # one it is cannot be known from this line. Look ahead to the next
            # meaningful line: `- ` means list. Guessing map (the first version of
            # this) makes `attestations:` create an empty dict, and the list items
            # beneath it then have no parent key to attach to.
            nxt_meaningful = None
            for la in range(i, len(lines)):
                if lines[la].strip() and not lines[la].strip().startswith("#"):
                    nxt_meaningful = lines[la]
                    break

            if nxt_meaningful is not None and nxt_meaningful.strip().startswith("- "):
                parent[key] = []
                parent["__last__"] = key
                continue

            child = {}
            parent[key] = child
            parent["__last__"] = key
            stack.append((indent, child))
            continue

        parent[key] = _scalar(value)
        parent["__last__"] = key

    def clean(d):
        if isinstance(d, dict):
            return {k: clean(v) for k, v in d.items() if k != "__last__"}
        if isinstance(d, list):
            return [clean(x) for x in d]
        return d

    return clean(doc)


# ── Tier derivation (ADR-11) ─────────────────────────────────────────────────

def granted(caps, name):
    """A capability counts as granted when true, or attested with valid evidence.

    `attested` counting as granted is the whole point of the mechanism — some
    capabilities cannot be proven by a free CI check, and refusing to believe them
    would mean declaring a real capability false. What stops it becoming a
    loophole is that the attestation must exist, parse, and not be expired, and
    conformance level 3 checks exactly that.
    """
    v = (caps or {}).get(name)
    return v is True or v == "attested"


def derive_tier(caps):
    """A = the full quality chain. B = mechanical gates, no subagent chain.
    C = prose + standalone gate scripts. None = Sage cannot run here.

    Derived, never declared. A tier you can type is a tier you can be wrong
    about, and `claude-code/platform.yaml` said `tier: 1` because somebody typed
    a 1.
    """
    veto = granted(caps, "pre-tool-veto")
    post = granted(caps, "post-tool-events")
    sub = granted(caps, "subagent-dispatch")
    ctx = granted(caps, "context-injection")

    if veto and post and sub:
        return "A"
    if veto and ctx:
        return "B"
    if ctx:
        return "C"
    return None


TIER_MEANING = {
    "A": "full quality chain — mechanical gates AND independent subagent review",
    "B": "mechanical gates; no subagent chain (reviews are not independent)",
    "C": "prose + standalone gate scripts; nothing blocks an edit",
    None: "unsupported — Sage cannot deliver its instructions here",
}


# ── Loading ──────────────────────────────────────────────────────────────────

def contract_paths():
    out = []
    for p in sorted(PLATFORMS.glob("*/platform.yaml")):
        out.append(p)
    for p in sorted(PLATFORMS.glob("community/*/platform.yaml")):
        out.append(p)
    return out


def load(path):
    data = parse_contract(path.read_text(encoding="utf-8"))
    data["__path__"] = str(path.relative_to(REPO_ROOT))
    data["__community__"] = "/community/" in str(path).replace("\\", "/")
    return data


def load_all():
    return [load(p) for p in contract_paths()]


# ── Validation ───────────────────────────────────────────────────────────────

def validate(c):
    problems = []
    name = c.get("name", "?")
    path = c.get("__path__")

    version = c.get("contract-version")
    if version != CONTRACT_VERSION:
        problems.append(
            "%s (%s): contract-version is %r, expected %d. Schema v1 declared "
            "features; v2 declares the capabilities that decide enforcement. "
            "See runtime/platforms/CONTRACT.md."
            % (name, path, version, CONTRACT_VERSION))
        return problems  # everything below assumes v2

    caps = c.get("capabilities") or {}
    for cap in CAPABILITIES:
        if cap not in caps:
            problems.append("%s: capability %r is not declared. Declare it — "
                            "`false` is an answer, silence is not." % (name, cap))
        elif caps[cap] not in VALID_VALUES:
            problems.append("%s: capability %r is %r; must be true, false, or "
                            "attested." % (name, cap, caps[cap]))
    for cap in caps:
        if cap not in CAPABILITIES:
            problems.append("%s: unknown capability %r (vocabulary is fixed; "
                            "adding one means teaching contract.py what it "
                            "means for enforcement)" % (name, cap))

    # Every `attested` needs evidence, and the evidence needs to be real.
    attestations = {a.get("capability"): a for a in (c.get("attestations") or [])
                    if isinstance(a, dict)}
    for cap, value in caps.items():
        if value != "attested":
            continue
        att = attestations.get(cap)
        if not att:
            problems.append(
                "%s: %r is `attested` with no attestation entry. That is just "
                "`true` wearing a costume." % (name, cap))
            continue
        ev = att.get("evidence")
        if not ev:
            problems.append("%s: attestation for %r has no `evidence:`" % (name, cap))
        elif not (REPO_ROOT / ev).is_file():
            problems.append("%s: attestation for %r points at %s, which does not "
                            "exist" % (name, cap, ev))
        if not att.get("expires-release"):
            problems.append(
                "%s: attestation for %r has no `expires-release:`. C15: no "
                "evergreen hand-waves — an attestation that never expires is a "
                "claim nobody will ever re-check." % (name, cap))

    # The legacy hand-set tier, if still present, must agree with the derived one.
    derived = derive_tier(caps)
    legacy = c.get("tier")
    if legacy is not None:
        legacy_letter = {1: "A", 2: "C", 3: "C"}.get(legacy, str(legacy))
        if legacy_letter != derived:
            problems.append(
                "%s: legacy `tier: %s` disagrees with the derived tier %s. The "
                "derived value wins — remove the legacy field. (This is the "
                "mismatch warning ADR-11 allows for one release.)"
                % (name, legacy, derived))

    if derived is None:
        problems.append(
            "%s: derives to NO tier — it cannot even inject context, so Sage "
            "cannot deliver its instructions there at all." % name)

    return problems


def expired_attestations(c, current_release):
    """Attestations whose expires-release is at or below the release being cut."""
    out = []
    try:
        cur = tuple(int(x) for x in str(current_release).split(".")[:2])
    except ValueError:
        return out
    for a in (c.get("attestations") or []):
        if not isinstance(a, dict):
            continue
        exp = a.get("expires-release")
        if not exp:
            continue
        try:
            e = tuple(int(x) for x in str(exp).split(".")[:2])
        except ValueError:
            continue
        if cur >= e:
            out.append(a)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--show", metavar="PLATFORM")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not (args.check or args.show or args.json):
        ap.error("choose --check, --show, or --json")

    try:
        contracts = load_all()
    except ContractError as e:
        print("❌ FAIL — a contract does not parse: %s" % e, file=sys.stderr)
        return 1

    if args.json:
        out = []
        for c in contracts:
            caps = c.get("capabilities") or {}
            out.append({
                "name": c.get("name"),
                "path": c.get("__path__"),
                "community": c.get("__community__"),
                "capabilities": caps,
                "tier": derive_tier(caps),
                "maintainer": c.get("maintainer"),
                "supported-os": c.get("supported-os"),
            })
        print(json.dumps(out, indent=2))
        return 0

    if args.show:
        for c in contracts:
            if c.get("name") != args.show:
                continue
            caps = c.get("capabilities") or {}
            tier = derive_tier(caps)
            print("%s  (%s)" % (c["name"], c["__path__"]))
            print("  derived tier: %s — %s" % (tier or "unsupported", TIER_MEANING[tier]))
            for cap, why in CAPABILITIES.items():
                v = caps.get(cap, "—")
                mark = "✅" if v is True else ("📝" if v == "attested" else "❌")
                print("  %s %-24s %-9s %s" % (mark, cap, str(v), why))
            return 0
        print("no contract named %r" % args.show, file=sys.stderr)
        return 1

    problems = []
    for c in contracts:
        problems.extend(validate(c))

    if problems:
        print("❌ FAIL — the capability contract does not hold (%d):\n" % len(problems),
              file=sys.stderr)
        for p in problems:
            print("  • %s" % p, file=sys.stderr)
        print("\n  ADR-11: a declared capability nothing checks is the pre-1.2.0 "
              "mistake with better formatting.", file=sys.stderr)
        return 1

    print("OK — %d contract(s) parse; tiers derive; no legacy mismatches." % len(contracts))
    for c in sorted(contracts, key=lambda x: (x["__community__"], x.get("name") or "")):
        tier = derive_tier(c.get("capabilities") or {})
        print("     %-14s tier %s%s" % (c.get("name"), tier or "—",
                                        "  (community)" if c["__community__"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
