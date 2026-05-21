"""Tests for the generated app-builder skill package."""

from __future__ import annotations

from pathlib import Path

from workspace_mcp.app_builder.skill_generator import check_skill


def test_generated_app_builder_skill_is_current() -> None:
    """The installable skill should stay in sync with MCP resources."""
    repo_root = Path(__file__).resolve().parents[1]

    assert check_skill(repo_root) == []
