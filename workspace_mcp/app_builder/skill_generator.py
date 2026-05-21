"""Generate the installable OpenBB app-builder skill from MCP resources."""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_URL = "https://github.com/OpenBB-finance/workspace-mcp"
RESOURCE_REGISTRY = Path("workspace_mcp/app_builder/resources.py")
RESOURCE_DIR = Path("workspace_mcp/app_builder/resources")
SKILL_DIR = Path(".claude/skills/openbb-app-builder")
GENERATED_MARKER = (
    "<!-- Generated from workspace_mcp/app_builder/resources by "
    "workspace_mcp/app_builder/skill_generator.py. Do not edit by hand. -->"
)


@dataclass(frozen=True)
class CatalogResource:
    """Resource metadata parsed from the MCP app-builder registry."""

    uri: str
    title: str
    description: str
    relative_path: str

    @property
    def reference_path(self) -> Path:
        """Return this resource's generated skill reference path."""
        return Path("references") / self.relative_path


def expected_skill_files(repo_root: Path) -> dict[Path, str]:
    """Return the generated skill files keyed by repository-relative path."""
    resources = parse_resource_registry(repo_root / RESOURCE_REGISTRY)
    files: dict[Path, str] = {
        SKILL_DIR / "SKILL.md": skill_body(resources),
    }

    for resource in resources:
        source_path = repo_root / RESOURCE_DIR / resource.relative_path
        source_body = source_path.read_text(encoding="utf-8").strip()
        reference_body = "\n".join(
            [
                GENERATED_MARKER,
                f"<!-- Source URI: {resource.uri} -->",
                f"<!-- Source file: {RESOURCE_DIR / resource.relative_path} -->",
                "",
                source_body,
                "",
            ]
        )
        files[SKILL_DIR / resource.reference_path] = reference_body

    return files


def write_skill(repo_root: Path) -> None:
    """Write the generated skill package to disk."""
    files = expected_skill_files(repo_root)
    for relative_path, content in files.items():
        path = repo_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    remove_stale_generated_files(repo_root, set(files))


def check_skill(repo_root: Path) -> list[str]:
    """Return a list of generation drift messages."""
    expected = expected_skill_files(repo_root)
    problems: list[str] = []

    for relative_path, expected_content in expected.items():
        path = repo_root / relative_path
        if not path.exists():
            problems.append(f"missing: {relative_path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected_content:
            problems.append(f"stale: {relative_path}")

    generated_dir = repo_root / SKILL_DIR
    if generated_dir.exists():
        for path in sorted(generated_dir.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(repo_root)
            if relative_path in expected:
                continue
            content = path.read_text(encoding="utf-8")
            if GENERATED_MARKER in content:
                problems.append(f"stale generated file: {relative_path}")

    return problems


def remove_stale_generated_files(repo_root: Path, expected: set[Path]) -> None:
    """Remove generated files that no longer correspond to registered resources."""
    generated_dir = repo_root / SKILL_DIR
    if not generated_dir.exists():
        return

    for path in sorted(generated_dir.rglob("*"), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
            continue

        relative_path = path.relative_to(repo_root)
        if relative_path in expected:
            continue
        content = path.read_text(encoding="utf-8")
        if GENERATED_MARKER in content:
            path.unlink()


def parse_resource_registry(path: Path) -> tuple[CatalogResource, ...]:
    """Parse AppBuilderResource entries from resources.py without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        value: ast.AST | None = None
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_INITIAL_RESOURCES"
            for target in node.targets
        ):
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_INITIAL_RESOURCES"
        ):
            value = node.value

        if value is None:
            continue
        if not isinstance(value, ast.Tuple):
            raise ValueError("_INITIAL_RESOURCES must be a tuple")
        return tuple(parse_resource_call(item) for item in value.elts)

    raise ValueError("Could not find _INITIAL_RESOURCES in resource registry")


def parse_resource_call(node: ast.AST) -> CatalogResource:
    """Parse one AppBuilderResource(...) call."""
    if not isinstance(node, ast.Call):
        raise ValueError("Resource registry entries must be AppBuilderResource calls")
    if not isinstance(node.func, ast.Name) or node.func.id != "AppBuilderResource":
        raise ValueError("Resource registry entries must be AppBuilderResource calls")

    kwargs = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords if kw.arg}
    return CatalogResource(
        uri=kwargs["uri"],
        title=kwargs["title"],
        description=kwargs["description"],
        relative_path=kwargs["relative_path"],
    )


def skill_body(resources: tuple[CatalogResource, ...]) -> str:
    """Build SKILL.md content for the generated installable skill."""
    reference_rows = "\n".join(
        f"| `{resource.uri}` | `{resource.reference_path.as_posix()}` |"
        for resource in resources
    )

    return f"""---
name: openbb-app-builder
description: Build, review, debug, or extend OpenBB Workspace app backends, widgets.json, apps.json, widget parameters, dashboard layouts, and validation workflows. Use this for custom Workspace apps or converting HTTP APIs into Workspace widgets.
metadata:
  short-description: Build OpenBB Workspace apps
---

{GENERATED_MARKER}

# OpenBB App Builder

This installable skill is generated from the app-builder resource catalog in
`{REPO_URL}`. The MCP resources are the source of truth; this skill is an
offline compatibility package for agents that support `npx skills add`.

## Preferred Path

When Workspace MCP is available, read the live MCP resource index first:

`openbb://workspace/app-builder/index`

Then follow the resource it routes you to. The live MCP resources should win
over this generated copy if they differ.

## Offline Fallback

If MCP resources are unavailable, use the generated references bundled with
this skill. They mirror the registered Workspace MCP resources at generation
time.

| MCP resource | Bundled reference |
|--------------|-------------------|
{reference_rows}
"""


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the generated skill is current without writing files",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root; defaults to this file's workspace-mcp checkout",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    if args.check:
        problems = check_skill(repo_root)
        if problems:
            print("Generated app-builder skill is out of date:", file=sys.stderr)
            for problem in problems:
                print(f"- {problem}", file=sys.stderr)
            print(
                "Run: uv run python workspace_mcp/app_builder/skill_generator.py",
                file=sys.stderr,
            )
            return 1
        print("Generated app-builder skill is current.")
        return 0

    write_skill(repo_root)
    print(f"Wrote generated skill to {SKILL_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
