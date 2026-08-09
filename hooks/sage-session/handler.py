"""sage-session — full Sage session-init as a Hermes gateway hook.

Port of runtime/platforms/claude-code/hooks/sage-session-init.sh to the
gateway observer surface (gateway/hooks.py: HOOK.yaml + handler.py;
session:start / session:end fire on the gateway; emit() discards returns, so
structured context is delivered through .sage/gates/session-pickup.md, which
the eager core tells the agent to read at session start — the same split
every Sage platform uses, adapted honestly to an observer-only surface).

Canon behavior, 1:1 where the surface allows:
  1. Parallel-session collision guard — .sage/.session-lock (pid/toplevel/
     updated_at), git-gated, EPERM-vs-ESRCH liveness, 6h stale backstop,
     .gitignore coverage. Warns, never blocks.
  2. Worktree memory directive — in a linked worktree, point sage-memory at
     the MAIN checkout root (sage_memory_set_project) so both share one store.
  3. Active work scan — frontmatter title/status/phase from plan/spec/brief.
  4. Project docs count (.sage/docs/*.md).
  5. Recent decisions (### / ## headings, tail 3).
  6. session:end — append the close to .sage/gates/session-log.

Errors are swallowed by design (and by the gateway): a session hook must
never break a session.
"""

from __future__ import annotations

import datetime
import glob
import os
import re
import subprocess
import time

STALE_SECONDS = 21600  # 6h backstop for a recycled pid


def _root(context):
    return os.path.abspath(os.getcwd())


def _git(root, *args):
    try:
        p = subprocess.run(["git", "-C", root, *args],
                           capture_output=True, text=True, timeout=5)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True   # EPERM — alive, foreign user
    except (ProcessLookupError, ValueError, OverflowError):
        return False
    except OSError:
        return False


def _fm_field(path, name):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            head = fh.read(2048)
    except OSError:
        return ""
    m = re.search(r"^\s*%s\s*:\s*\"?([^\"\n]+?)\"?\s*$" % re.escape(name),
                  head, re.M)
    return m.group(1).strip() if m else ""


def _collision_guard(root, sage_dir, warnings):
    if not _git(root, "rev-parse", "--git-dir").strip():
        return
    lock = os.path.join(sage_dir, ".session-lock")
    toplevel = _git(root, "rev-parse", "--show-toplevel").strip()

    # Keep the lock out of git.
    if not _git(root, "check-ignore", "-q", lock).strip() \
            and _git(root, "check-ignore", "-q", lock) is not None:
        gi = os.path.join(sage_dir, ".gitignore")
        try:
            need = True
            if os.path.isfile(gi):
                with open(gi, encoding="utf-8", errors="replace") as fh:
                    if ".session-lock" in fh.read().splitlines():
                        need = False
            if need:
                with open(gi, "a", encoding="utf-8") as fh:
                    fh.write(".session-lock\n")
        except OSError:
            pass

    my_pid = os.getpid()
    if os.path.isfile(lock):
        l_pid = l_top = l_upd = ""
        try:
            with open(lock, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("pid="):
                        l_pid = line[4:].strip()
                    elif line.startswith("toplevel="):
                        l_top = line[9:].strip()
                    elif line.startswith("updated_at="):
                        l_upd = line[11:].strip()
        except OSError:
            pass
        alive = _pid_alive(l_pid) if l_pid else False
        try:
            if l_upd and (int(time.time()) - int(l_upd)) > STALE_SECONDS:
                alive = False
        except ValueError:
            pass
        if alive and l_pid != str(my_pid) and l_top == toplevel:
            warnings.append(
                "⚠ Another Sage session appears active in this checkout. "
                "Parallel sessions in one directory clobber each other. "
                "For an isolated session: sage worktree <name>")

    try:
        with open(lock, "w", encoding="utf-8") as fh:
            fh.write("pid=%s\ntoplevel=%s\nupdated_at=%s\n"
                     % (my_pid, toplevel, int(time.time())))
    except OSError:
        pass


def _worktree_memory_directive(root):
    if not _git(root, "rev-parse", "--git-dir").strip():
        return ""
    gd = _git(root, "rev-parse", "--git-dir").strip()
    gcd = _git(root, "rev-parse", "--git-common-dir").strip()
    if not gd or not gcd:
        return ""
    gd_abs = os.path.realpath(os.path.join(root, gd)) \
        if not os.path.isabs(gd) else os.path.realpath(gd)
    gcd_abs = os.path.realpath(os.path.join(root, gcd)) \
        if not os.path.isabs(gcd) else os.path.realpath(gcd)
    if gd_abs == gcd_abs:
        return ""
    main_root = ""
    for line in _git(root, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            main_root = line.split(" ", 1)[1].strip()
            break
    if not main_root:
        main_root = os.path.dirname(gcd_abs)
    return ("Memory (worktree): before any other sage_memory tool, call "
            "sage_memory_set_project with this MAIN checkout root as the path: "
            "%s — so reads and writes share the main checkout's store. This "
            "worktree's own .sage-memory is empty and disposable; never copy "
            "or harvest it." % main_root)


def _active_work(sage_dir):
    out, count, in_progress = [], 0, ""
    for d in sorted(glob.glob(os.path.join(sage_dir, "work", "*/"))):
        for artifact in ("plan.md", "spec.md", "brief.md"):
            f = os.path.join(d, artifact)
            if not os.path.isfile(f):
                continue
            title = _fm_field(f, "title") or os.path.basename(d.rstrip("/\\"))
            status = _fm_field(f, "status") or "unknown"
            phase = _fm_field(f, "phase")
            out.append("  - %s [%s, %s] — %s" % (title, status, phase, f))
            count += 1
            if status == "in-progress":
                in_progress = title
            break
    return out, count, in_progress


def _recent_decisions(sage_dir):
    decisions = os.path.join(sage_dir, "decisions.md")
    if not os.path.isfile(decisions):
        return []
    try:
        with open(decisions, encoding="utf-8", errors="replace") as fh:
            heads = [ln for ln in fh if ln.startswith(("### ", "## 20"))]
    except OSError:
        return []
    return [h.rstrip() for h in heads[-3:]]


async def handle(event_type, context):
    try:
        root = _root(context or {})
        sage_dir = os.path.join(root, ".sage")
        if not os.path.isdir(sage_dir):
            return
        gates_dir = os.path.join(sage_dir, "gates")
        os.makedirs(gates_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if event_type == "session:start":
            warnings = []
            _collision_guard(root, sage_dir, warnings)
            worktree_note = _worktree_memory_directive(root)
            work, count, in_progress = _active_work(sage_dir)
            docs = len(glob.glob(os.path.join(sage_dir, "docs", "*.md")))
            recent = _recent_decisions(sage_dir)

            note = os.path.join(gates_dir, "session-pickup.md")
            with open(note, "w", encoding="utf-8") as fh:
                fh.write("## Sage Context (auto-written by sage-session, %s)\n\n" % ts)
                for w in warnings:
                    fh.write(w + "\n\n")
                if worktree_note:
                    fh.write(worktree_note + "\n\n")
                if count:
                    if in_progress:
                        fh.write("Sage: %s is in progress.\n\n" % in_progress)
                    fh.write("Active work (%d):\n" % count)
                    fh.write("\n".join(work) + "\n")
                else:
                    fh.write("Sage: No active work. Ready for a new task.\n")
                if docs:
                    fh.write("\nProject docs: %d files in .sage/docs/\n" % docs)
                if recent:
                    fh.write("\nRecent decisions:\n" + "\n".join(recent) + "\n")
                fh.write("\nUse /sage, /sage-build, /sage-fix, /sage-architect, "
                         "/sage-review, or /sage-learn.\n")

        elif event_type == "session:end":
            with open(os.path.join(gates_dir, "session-log"), "a",
                      encoding="utf-8") as fh:
                fh.write("%s session:end %s\n"
                         % (ts, (context or {}).get("session_id", "")))
    except Exception:
        return
