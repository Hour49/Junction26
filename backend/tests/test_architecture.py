"""Dependency rule (docs/ENGINEERING.md section 1): core imports nothing from the outer layers."""

import ast
from pathlib import Path

APP = Path(__file__).parent.parent / "app"

FORBIDDEN_IN_CORE = (
    "app.api",
    "app.adapters",
    "app.settings",
    "app.main",
    "fastapi",
    "starlette",
    "uvicorn",
    "pydantic_settings",
    "httpx",
    "httpx2",
    "requests",
    "anthropic",
    "openai",
    "google.genai",
)


def forbidden_imports(source: str, module: str) -> list[str]:
    """Dotted names imported by `source` (the code of `module`) that core must not use."""
    package = module.split(".")[:-1]
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            prefix = ".".join([*base, *([node.module] if node.module else [])])
            names += [f"{prefix}.{alias.name}" for alias in node.names]
    return [n for n in names if any(n == f or n.startswith(f + ".") for f in FORBIDDEN_IN_CORE)]


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(APP.parent).with_suffix("").parts)


def test_core_imports_nothing_from_outer_layers() -> None:
    violations = [
        f"{path.relative_to(APP.parent)}: {name}"
        for path in sorted((APP / "core").rglob("*.py"))
        for name in forbidden_imports(path.read_text(), module_name(path))
    ]
    assert violations == []


def test_scanner_flags_outer_layer_imports() -> None:
    source = "\n".join(
        [
            "import fastapi",
            "from ..adapters import llm",
            "from app import settings",
            "import openai.types",
            "from httpx2 import Client",
        ]
    )
    assert forbidden_imports(source, "app.core.rules") == [
        "fastapi",
        "app.adapters.llm",
        "app.settings",
        "openai.types",
        "httpx2.Client",
    ]


def test_scanner_allows_stdlib_and_core_imports() -> None:
    source = "import dataclasses\nfrom typing import Protocol\nfrom .errors import NotFoundError\n"
    assert forbidden_imports(source, "app.core.rules") == []
