"""Configurable OpenViking learning recall adapter.

The adapter has no deployment defaults for resource scope or identity.  Those
values must be supplied by the caller after resolving local configuration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

from ..learning_contracts import (
    MAX_DIAGNOSTIC_BYTES,
    LearningContext,
    LearningContractError,
    RecallRecord,
    RecallResult,
)


_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s*)?(?:\*\*)?"
    r"(?P<label>prevention(?: rule)?|rationale|why)"
    r"(?:\*\*)?\s*:\s*(?P<value>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TransportResponse:
    status_code: int
    payload: object
    text: str = ""


class HTTPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object] | None,
        timeout: float,
    ) -> TransportResponse: ...


@dataclass(frozen=True)
class UrllibTransport:
    default_headers: Mapping[str, str] | None = None

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        json_body: Mapping[str, object] | None,
        timeout: float,
    ) -> TransportResponse:
        merged_headers = dict(self.default_headers or {})
        merged_headers.update(headers)
        data = (
            None
            if json_body is None
            else json.dumps(dict(json_body)).encode("utf-8")
        )
        request = Request(
            url,
            data=data,
            headers=merged_headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=timeout)
            status_code = int(getattr(response, "status", 200))
            raw = response.read(1024 * 1024 + 1)
        except HTTPError as exc:
            status_code = exc.code
            raw = exc.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("OpenViking response exceeded 1 MiB")
        text = raw.decode("utf-8", errors="replace")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        return TransportResponse(status_code=status_code, payload=payload, text=text)


def _bounded(value: object, max_bytes: int) -> str:
    text = " ".join(str(value or "").split())
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    return encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()


def _required(value: object, field: str, max_bytes: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LearningContractError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized.encode("utf-8")) > max_bytes:
        raise LearningContractError(f"{field} exceeds {max_bytes} UTF-8 bytes")
    return normalized


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _pick(item: Mapping[str, object], metadata: Mapping[str, object], key: str, default=None):
    return item[key] if key in item else metadata.get(key, default)


def _title_from_uri(uri: str) -> str:
    leaf = unquote(uri.rstrip("/").rsplit("/", 1)[-1])
    if leaf.casefold().endswith(".md"):
        leaf = leaf[:-3]
    return leaf.replace("_", " ").replace("-", " ").strip() or "Stored learning"


def _learning_fields(item: Mapping[str, object], metadata: Mapping[str, object]) -> tuple[str, str]:
    prevention = _bounded(_pick(item, metadata, "prevention", ""), 2048)
    rationale = _bounded(_pick(item, metadata, "rationale", ""), 1024)
    raw_content = _pick(item, metadata, "content", "")
    if not raw_content:
        raw_content = item.get("overview") or item.get("abstract") or ""
    content = str(raw_content or "")
    for line in content.splitlines():
        match = _FIELD_RE.match(line)
        if not match:
            continue
        label = match.group("label").casefold()
        value = match.group("value")
        if label.startswith("prevention") and not prevention:
            prevention = _bounded(value, 2048)
        elif label in {"why", "rationale"} and not rationale:
            rationale = _bounded(value, 1024)
    if not rationale:
        rationale = _bounded(content, 1024)
    return prevention, rationale


@dataclass(frozen=True)
class OpenVikingBackend:
    base_url: str
    resource_uri: str
    user: str
    agent_id: str
    timeout: float = 2.0
    transport: HTTPTransport | None = None

    def __post_init__(self) -> None:
        base_url = _required(self.base_url, "base_url", 2048).rstrip("/")
        if not base_url.startswith(("http://", "https://")):
            raise LearningContractError("base_url must use http or https")
        resource_uri = _required(self.resource_uri, "resource_uri", 2048).rstrip("/")
        if not resource_uri.startswith("viking://resources/"):
            raise LearningContractError("resource_uri must be a resources URI")
        if "?" in resource_uri or "#" in resource_uri:
            raise LearningContractError("resource_uri must not contain query or fragment")
        user = _required(self.user, "user")
        agent_id = _required(self.agent_id, "agent_id")
        if any(character.isspace() for character in user + agent_id):
            raise LearningContractError("user and agent_id must not contain whitespace")
        if not isinstance(self.timeout, (int, float)) or not 0 < float(self.timeout) <= 60:
            raise LearningContractError("timeout must be between 0 and 60 seconds")
        object.__setattr__(self, "base_url", base_url)
        object.__setattr__(self, "resource_uri", resource_uri)
        object.__setattr__(self, "user", user)
        object.__setattr__(self, "agent_id", agent_id)
        object.__setattr__(self, "timeout", float(self.timeout))
        if self.transport is None:
            object.__setattr__(self, "transport", UrllibTransport())

    def _failure(self, query: str, diagnostic: object) -> RecallResult:
        return RecallResult(
            query=query,
            backend="openviking",
            diagnostics=(_bounded(f"OpenViking recall unavailable: {diagnostic}", MAX_DIAGNOSTIC_BYTES),),
            ok=False,
        )

    def _inside_resource(self, uri: str) -> bool:
        if not uri.startswith(self.resource_uri + "/"):
            return False
        leaf = uri.rstrip("/").rsplit("/", 1)[-1].casefold()
        if leaf in {".abstract.md", ".overview.md", ".read.md", ".full.md"}:
            return False
        return leaf.endswith(".md")

    def _read_content(
        self, uri: str, headers: Mapping[str, str], timeout: float
    ) -> str:
        """Best-effort L2 read for search hits that contain only an abstract."""
        try:
            assert self.transport is not None
            response = self.transport.request(
                "GET",
                f"{self.base_url}/api/v1/content/read?uri={quote(uri, safe='')}",
                headers=headers,
                json_body=None,
                timeout=timeout,
            )
            if response.status_code >= 400 or not isinstance(response.payload, Mapping):
                return ""
            if response.payload.get("status") == "error":
                return ""
            result = response.payload.get("result")
            if isinstance(result, str):
                return result
            if isinstance(result, Mapping):
                content = result.get("content") or result.get("text")
                return content if isinstance(content, str) else ""
        except Exception:
            return ""
        return ""

    def search_learnings(
        self, query: str, context: LearningContext, limit: int = 5
    ) -> RecallResult:
        bounded_limit = min(10, max(1, int(limit)))
        headers = {
            "Content-Type": "application/json",
            "X-OpenViking-User": self.user,
            "X-OpenViking-Actor-Peer": self.agent_id,
        }
        body = {
            "query": query,
            "target_uri": self.resource_uri,
            "context_type": "resource",
            "limit": bounded_limit,
        }
        try:
            assert self.transport is not None
            response = self.transport.request(
                "POST",
                f"{self.base_url}/api/v1/search/find",
                headers=headers,
                json_body=body,
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                return self._failure(
                    query,
                    f"HTTP {response.status_code}: {_bounded(response.text, 240)}",
                )
            payload = response.payload
            if not isinstance(payload, Mapping) or payload.get("status") == "error":
                return self._failure(query, "invalid or error response")
            result = payload.get("result")
            if not isinstance(result, Mapping):
                return self._failure(query, "result must be an object")
            items = result.get("resources", [])
            if not isinstance(items, list):
                return self._failure(query, "resource results must be a list")

            records: list[RecallRecord] = []
            seen = set(context.seen_record_ids)
            for raw_item in items:
                if not isinstance(raw_item, Mapping):
                    continue
                uri_raw = raw_item.get("uri") or raw_item.get("id")
                if not isinstance(uri_raw, str):
                    continue
                uri = uri_raw.strip()
                if not self._inside_resource(uri) or uri in seen:
                    continue
                metadata = _mapping(raw_item.get("metadata"))
                item = dict(raw_item)
                has_structured_fields = bool(
                    _pick(item, metadata, "prevention", "")
                    or _pick(item, metadata, "rationale", "")
                )
                if not item.get("content") and not has_structured_fields:
                    read_timeout = max(0.05, self.timeout / (bounded_limit + 1))
                    full_content = self._read_content(uri, headers, read_timeout)
                    if full_content:
                        item["content"] = full_content
                prevention, rationale = _learning_fields(item, metadata)
                tags = _pick(raw_item, metadata, "tags", ["self-learning"])
                if isinstance(tags, list) and "self-learning" not in tags:
                    tags = ["self-learning", *tags]
                status = _pick(raw_item, metadata, "status", "active")
                records.append(
                    RecallRecord(
                        id=uri,
                        title=_pick(raw_item, metadata, "title", _title_from_uri(uri)),
                        prevention=prevention,
                        rationale=rationale,
                        score=_pick(raw_item, metadata, "score", 0.0),
                        tags=tags,
                        status=status,
                        scope=_pick(raw_item, metadata, "scope", "global"),
                        project=_pick(raw_item, metadata, "project"),
                        platforms=_pick(raw_item, metadata, "platforms", ()),
                        capabilities=_pick(raw_item, metadata, "capabilities", ()),
                        providers=_pick(raw_item, metadata, "providers", ()),
                        paths=_pick(raw_item, metadata, "paths", ()),
                        dedupe_key=_pick(raw_item, metadata, "dedupe_key", ""),
                        superseded_by=_pick(raw_item, metadata, "superseded_by"),
                        corrects=_pick(raw_item, metadata, "corrects"),
                    )
                )
                seen.add(uri)
                if len(records) >= bounded_limit:
                    break
            return RecallResult(
                query=query,
                records=tuple(records),
                backend="openviking",
            )
        except Exception as exc:
            return self._failure(query, exc)

    def store_learning(self, record: RecallRecord) -> RecallRecord:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def update_learning(self, record_id: str, record: RecallRecord) -> RecallRecord:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def invalidate_learning(self, record_id: str, correction_id: str) -> bool:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def link_learning(self, source_id: str, target_id: str, relation: str) -> bool:
        raise NotImplementedError("hook recall adapter does not author learnings")

    def list_learnings(
        self, filters: Mapping[str, object] | None = None
    ) -> tuple[RecallRecord, ...]:
        raise NotImplementedError("hook recall adapter does not browse learnings")
