#!/usr/bin/env python3
"""Strict per-workspace memory namespace (spec 5.8.5-7).

The isolation mechanism is the database FILE, never a tag: every session
resolves exactly ``<workspace>/.sage-memory/memory.db`` and verifies the
returned handle against it. A backend that returns anything else — a global
home, a sibling workspace, a tag-filtered shared store — fails visibly.
Junction/symlink escapes are rejected at resolution.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sqlite3
from datetime import datetime, timezone
from typing import Optional


class MemoryNamespaceError(RuntimeError):
    """The memory namespace contract was violated; the session must stop."""


def _norm(value) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(value)))


def _link_components(path) -> list:
    """Path components that are symlinks/junctions/reparse points.

    Direct lstat per component — no spelling comparison, so 8.3 short names
    and SUBST drives (legitimate spellings, not links) do not false-fire.
    """

    import stat as stat_mod

    hits = []
    current = pathlib.Path(os.path.abspath(path))
    while True:
        try:
            st = os.lstat(current)
        except OSError:
            break
        if stat_mod.S_ISLNK(st.st_mode):
            hits.append(current)
        elif (
            os.name == "nt"
            and getattr(st, "st_file_attributes", 0) & 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
        ):
            hits.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return hits


def resolve_memory_db(workspace) -> pathlib.Path:
    """The exact bound database path, with link escapes rejected.

    The workspace must already exist — the plugin only ever resolves the DB
    for a real bound workspace, and a silent create would hide a wrong root.
    Both the workspace chain AND the .sage-memory component are checked, so
    a junction inside the workspace cannot redirect the database elsewhere.
    """

    workspace = pathlib.Path(workspace)
    if _link_components(workspace):
        raise MemoryNamespaceError(
            "workspace resolves through a link/junction — refusing: %s" % workspace
        )
    try:
        resolved = workspace.resolve(strict=True)
    except OSError as exc:
        raise MemoryNamespaceError(
            "workspace does not exist or does not resolve: %s" % exc
        ) from exc
    memdir = resolved / ".sage-memory"
    if memdir.exists() and _link_components(memdir):
        raise MemoryNamespaceError(
            ".sage-memory resolves through a link/junction — refusing: %s" % memdir
        )
    db = memdir / "memory.db"
    real_db = db.resolve(strict=False)
    if _norm(real_db) != _norm(db) or not _norm(real_db).startswith(
        _norm(resolved) + os.sep
    ):
        raise MemoryNamespaceError("memory database escapes the bound workspace")
    return db


def verify_session_db(returned, workspace) -> pathlib.Path:
    """The returned handle must BE the bound workspace database."""

    if returned is None:
        raise MemoryNamespaceError(
            "no strict per-workspace database was returned — a global or "
            "shared memory home does not satisfy the namespace contract"
        )
    bound = resolve_memory_db(workspace)
    if _norm(returned) != _norm(bound):
        raise MemoryNamespaceError(
            "returned database is not the bound workspace database: %s" % returned
        )
    return bound


class WorkspaceMemoryStore:
    """The honest strict backend: one SQLite file per bound workspace."""

    def __init__(self, workspace) -> None:
        self.db_path = resolve_memory_db(workspace)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(os.fspath(self.db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS memories (key TEXT PRIMARY KEY, value TEXT)"
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_memories (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                scope TEXT NOT NULL CHECK (scope = 'project'),
                created_at TEXT NOT NULL
            )"""
        )
        self._conn.commit()

    def remember(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO memories (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def recall(self, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM memories WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def store(self, *, title: str, content: str, tags=None) -> dict:
        """Store one deduplicated project-only knowledge record."""

        normalized_tags = sorted(
            {str(tag).strip().casefold() for tag in (tags or []) if str(tag).strip()}
        )
        identity = hashlib.sha256(
            json.dumps(
                [title.strip(), content.strip(), normalized_tags],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        created = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR IGNORE INTO knowledge_memories
               (id, title, content, tags_json, scope, created_at)
               VALUES (?, ?, ?, ?, 'project', ?)""",
            (
                identity,
                title.strip(),
                content.strip(),
                json.dumps(normalized_tags, ensure_ascii=False),
                created,
            ),
        )
        self._conn.commit()
        row = self._conn.execute(
            """SELECT id, title, content, tags_json, scope, created_at
               FROM knowledge_memories WHERE id = ?""",
            (identity,),
        ).fetchone()
        return self._record(row)

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        filter_tags=None,
        boost_tags=None,
    ) -> list[dict]:
        """Deterministic project-only keyword search over this database file."""

        required = {str(tag).strip().casefold() for tag in (filter_tags or []) if str(tag).strip()}
        boosted = {str(tag).strip().casefold() for tag in (boost_tags or []) if str(tag).strip()}
        terms = [term.casefold() for term in query.split() if term.strip()]
        rows = self._conn.execute(
            """SELECT id, title, content, tags_json, scope, created_at
               FROM knowledge_memories WHERE scope = 'project'"""
        ).fetchall()
        ranked = []
        for row in rows:
            record = self._record(row)
            tags = set(record["tags"])
            if not required.issubset(tags):
                continue
            title = record["title"].casefold()
            content = record["content"].casefold()
            searchable = "%s %s %s" % (title, content, " ".join(tags))
            if terms and not all(term in searchable for term in terms):
                continue
            score = sum(3 * title.count(term) + content.count(term) for term in terms)
            score += 2 * len(tags.intersection(boosted))
            record["score"] = score
            ranked.append(record)
        ranked.sort(
            key=lambda record: (
                -record["score"],
                record["title"].casefold(),
                record["id"],
            )
        )
        return ranked[:limit]

    @staticmethod
    def _record(row) -> dict:
        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "tags": json.loads(row[3]),
            "scope": row[4],
            "created_at": row[5],
        }

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "WorkspaceMemoryStore":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
