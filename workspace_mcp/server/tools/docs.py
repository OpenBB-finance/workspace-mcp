"""App-builder documentation discovery and reading tools."""

from __future__ import annotations

import re
from typing import Any

from fastmcp import FastMCP

from workspace_mcp.app_builder import AppBuilderResource, app_builder_resources
from workspace_mcp.app_builder.resources import MIME_TYPE
from workspace_mcp.server._guidance import describe_tool
from workspace_mcp.server._helpers import ToolResponse, invalid_request


MAX_LIMIT = 10
DEFAULT_LIMIT = 5


def register(server: FastMCP) -> None:
    @server.tool(
        description=describe_tool(
            "Search OpenBB Workspace app-builder documentation resources: overview docs, backend contract, widgets.json/apps.json specs, widget types, widget parameters, layout grid, examples, guides, and common validation errors.",
            "Use this before building, reviewing, debugging, or converting custom Workspace backends, widgets.json, or apps.json.",
        )
    )
    async def search_workspace_docs(
        query: str,
        limit: int | None = None,
    ) -> ToolResponse:
        """Search app-builder resources by title, description, URI, and content."""
        clean_query = query.strip()
        if not clean_query:
            return invalid_request(
                "search_workspace_docs",
                "search_workspace_docs requires a non-empty query.",
            )

        bounded_limit = _bounded_limit(limit)
        results = _search_resources(clean_query, bounded_limit)
        return {
            "ok": True,
            "command": "search_workspace_docs",
            "request_id": None,
            "message": f"Found {len(results)} Workspace documentation resources.",
            "data": {
                "query": clean_query,
                "results": results,
            },
            "error": None,
        }

    @server.tool(
        description=describe_tool(
            "Read one OpenBB Workspace app-builder documentation resource by exact openbb://workspace/... URI.",
            "Use after search_workspace_docs returns a relevant URI, or when the user names a known Workspace documentation URI.",
        )
    )
    async def read_workspace_doc(uri: str) -> ToolResponse:
        """Read one app-builder resource by URI."""
        clean_uri = uri.strip()
        resource = _resource_by_uri(clean_uri)
        if resource is None:
            return invalid_request(
                "read_workspace_doc",
                f"Unknown Workspace documentation resource URI: {clean_uri}",
            )

        content = resource.read()
        metadata, body = _split_frontmatter(content)
        related = _metadata_list(metadata.get("related"))
        return {
            "ok": True,
            "command": "read_workspace_doc",
            "request_id": None,
            "message": f"Read Workspace documentation resource: {resource.title}.",
            "data": {
                "resource": {
                    "uri": resource.uri,
                    "title": resource.title,
                    "description": resource.description,
                    "mime_type": MIME_TYPE,
                    "metadata": metadata,
                    "related": related,
                    "content": content,
                    "body": body,
                }
            },
            "error": None,
        }


def _bounded_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return min(max(limit, 1), MAX_LIMIT)


def _resource_by_uri(uri: str) -> AppBuilderResource | None:
    return next(
        (resource for resource in app_builder_resources() if resource.uri == uri),
        None,
    )


def _search_resources(query: str, limit: int) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    phrase = query.lower()
    scored: list[tuple[int, dict[str, Any]]] = []

    for resource in app_builder_resources():
        content = resource.read()
        metadata, body = _split_frontmatter(content)
        score = _resource_score(
            phrase=phrase,
            terms=terms,
            uri=resource.uri.lower(),
            title=resource.title.lower(),
            description=resource.description.lower(),
            content=content.lower(),
        )
        if score <= 0:
            continue

        scored.append(
            (
                score,
                {
                    "uri": resource.uri,
                    "title": resource.title,
                    "description": resource.description,
                    "score": score,
                    "snippet": _snippet(body, terms),
                    "metadata": metadata,
                    "related": _metadata_list(metadata.get("related")),
                },
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1]["title"]))
    return [item for _, item in scored[:limit]]


def _resource_score(
    *,
    phrase: str,
    terms: list[str],
    uri: str,
    title: str,
    description: str,
    content: str,
) -> int:
    score = 0
    for term in terms:
        if term in uri:
            score += 20
        if term in title:
            score += 20
        if term in description:
            score += 10
        if term in content:
            score += min(content.count(term), 5) * 3

    if phrase and phrase in f"{uri} {title}":
        score += 40
    if phrase and phrase in description:
        score += 20
    if phrase and phrase in content:
        score += 10
    return score


def _query_terms(query: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[a-z0-9][a-z0-9_.:/-]*", query.lower())
        if len(term) > 1
    ]


def _snippet(body: str, terms: list[str]) -> str:
    if not body:
        return ""

    compact_body = _compact_whitespace(body)
    compact_lower = compact_body.lower()
    match_index = -1
    for term in terms:
        match_index = compact_lower.find(term)
        if match_index >= 0:
            break

    if match_index < 0:
        return compact_body[:320]

    start = max(match_index - 120, 0)
    end = min(match_index + 240, len(compact_body))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(compact_body) else ""
    return f"{prefix}{compact_body[start:end]}{suffix}"


def _compact_whitespace(value: str) -> str:
    return " ".join(value.split())


def _split_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if end_index is None:
        return {}, content

    metadata = _parse_frontmatter(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).lstrip()
    return metadata, body


def _parse_frontmatter(lines: list[str]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    current_key: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ") and current_key:
            current = metadata.setdefault(current_key, [])
            if isinstance(current, list):
                current.append(stripped[2:].strip())
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        clean_value = value.strip()
        metadata[current_key] = clean_value if clean_value else []
    return metadata


def _metadata_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []
