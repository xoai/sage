#!/usr/bin/env python3
"""Level-3 conformance: an attestation is a loan, and loans mature (C15).

An `attested` capability says: this is real, no free check can prove it, and here
is a transcript. That is a legitimate answer — some platform behaviors can only
be established by running a session and watching what happens, and refusing to
believe them would mean declaring a real capability `false`.

What makes it honest rather than a loophole is that it expires. This script is
what makes the expiry real:

  * the attestation entry exists for every `attested` value
  * its evidence file exists on disk and is not empty
  * it names a `verified:` date and an `expires-release:`
  * that release has not yet arrived

An expired attestation FAILS. It does not warn. The whole point of C15's "no
evergreen hand-waves" is that a claim nobody ever re-checks is a claim that will
eventually be false without anybody noticing — which is the exact mechanism by
which the README came to advertise a 200-line eager layer that was 398 lines.

Exit: 0 all valid · 1 something is wrong · 3 nothing to check.
"""

import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "runtime" / "tools"))

import contract as C  # noqa: E402


def current_release():
    v = (REPO_ROOT / "VERSION").read_text().strip()
    return ".".join(v.split(".")[:2])


def main():
    if len(sys.argv) < 2:
        print("usage: check_attestations.py <platform>", file=sys.stderr)
        return 1
    want = sys.argv[1]

    for c in C.load_all():
        if c.get("name") != want:
            continue

        caps = c.get("capabilities") or {}
        attested = [k for k, v in caps.items() if v == "attested"]
        if not attested:
            return 3

        atts = {a.get("capability"): a for a in (c.get("attestations") or [])
                if isinstance(a, dict)}
        release = current_release()
        problems, good = [], []

        for cap in attested:
            a = atts.get(cap)
            if not a:
                problems.append("%s: `attested` with no attestation entry — that is "
                                "`true` wearing a costume" % cap)
                continue

            ev = a.get("evidence")
            if not ev:
                problems.append("%s: no evidence file named" % cap)
                continue
            path = REPO_ROOT / ev
            if not path.is_file():
                problems.append("%s: evidence %s does not exist" % (cap, ev))
                continue
            if path.stat().st_size < 200:
                problems.append("%s: evidence %s is nearly empty — an attestation "
                                "with no transcript attests to nothing" % (cap, ev))
                continue

            exp = a.get("expires-release")
            if not exp:
                problems.append("%s: no `expires-release:` (C15: no evergreen "
                                "hand-waves)" % cap)
                continue

            try:
                cur_t = tuple(int(x) for x in release.split("."))
                exp_t = tuple(int(x) for x in str(exp).split("."))
            except ValueError:
                problems.append("%s: unparseable release numbers (%s vs %s)"
                                % (cap, release, exp))
                continue

            if cur_t >= exp_t:
                problems.append(
                    "%s: attestation EXPIRED — verified %s, expires at release %s, "
                    "and we are cutting %s. Re-probe it or change the value to "
                    "`false`. An expired attestation is an unverified claim with a "
                    "date on it." % (cap, a.get("verified", "?"), exp, release))
                continue

            good.append("%s: attested %s, evidence %s, expires %s (current %s)"
                        % (cap, a.get("verified", "?"), ev, exp, release))

        if problems:
            for p in problems:
                print(p)
            return 1
        for g in good:
            print(g)
        return 0

    print("no contract named %r" % want, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
