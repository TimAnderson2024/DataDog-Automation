#!/usr/bin/env python3
"""Generate a Kubernetes ConfigMap `data:` section from .py files in ./scripts.

Usage:
  python scripts/generate_configmap_data.py [--out FILE]

Writes YAML mapping with a top-level `data:` key where each entry is the
filename -> literal block of the file contents. By default prints to stdout.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Dict, Set, List
import ast


def py_files(directory: Path) -> Iterable[Path]:
    for p in directory.glob("*.py"):
        if p.is_file():
            yield p


def parse_imports(path: Path) -> Set[str]:
    """Return a set of module basenames (no .py) that `path` imports from the same directory."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    imports: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                imports.add(name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                name = node.module.split(".")[0]
                imports.add(name)
    return imports


def topological_sort(files: List[Path]) -> List[Path]:
    # map stem -> Path
    name_map: Dict[str, Path] = {p.stem: p for p in files}
    # build dependency graph: file -> set of files it depends on (by stem)
    deps: Dict[str, Set[str]] = {}
    for p in files:
        imported = parse_imports(p)
        # keep only imports that refer to other files in this directory
        deps[p.stem] = {m for m in imported if m in name_map}

    # Kahn's algorithm
    inverse: Dict[str, Set[str]] = {k: set() for k in deps}
    for k, vs in deps.items():
        for v in vs:
            inverse[v].add(k)

    # nodes with no deps
    ready = [k for k, v in deps.items() if not v]
    result: List[Path] = []
    while ready:
        ready.sort()
        n = ready.pop(0)
        result.append(name_map[n])
        for m in sorted(inverse.get(n, [])):
            deps[m].discard(n)
            if not deps[m]:
                ready.append(m)

    if len(result) != len(files):
        # cycle or unresolved; fall back to deterministic alphabetical order
        return sorted(files, key=lambda p: p.name)

    return result


def to_block_scalar(text: str, indent: int = 4) -> str:
    # Return a literal block scalar (|-) with `indent` spaces prefixed to each content line.
    lines = text.splitlines()
    if not lines:
        return "|-\n"
    out = "|-\n"
    pad = " " * indent
    for line in lines:
        out += pad + line + "\n"
    return out


def generate_data_section(dir_path: Path) -> str:
    parts = ["data:"]
    files = list(py_files(dir_path))
    ordered = topological_sort(files)
    for p in ordered:
        key = p.name
        content = p.read_text(encoding="utf-8")
        # key is indented two spaces; indent block content two more spaces (total 4)
        parts.append(f"  {key}: {to_block_scalar(content, indent=4).rstrip()}\n")
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    parser = argparse.ArgumentParser(description="Generate ConfigMap data from scripts/*.py")
    parser.add_argument("--dir", "-d", default="scripts", help="Directory to read .py files from")
    parser.add_argument("--out", "-o", help="Write output to file instead of stdout")
    args = parser.parse_args(argv)

    dir_path = Path(args.dir)
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"Directory not found: {dir_path}", file=sys.stderr)
        return 2

    out = generate_data_section(dir_path)

    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
    else:
        print(out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
