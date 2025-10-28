#!/usr/bin/env python3
"""Compute deterministic hashes for dependency lock files."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Iterable


_REPO_ROOT = Path(__file__).resolve().parents[2]


def _existing_paths(raw_paths: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw in raw_paths:
        candidate = Path(raw)
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue
        if not resolved.is_file() or resolved in seen:
            continue
        seen.add(resolved)
        paths.append(resolved)
    return paths


def _normalize_for_digest(path: Path) -> str:
    try:
        relative = path.resolve().relative_to(_REPO_ROOT)
    except ValueError:
        relative = path.resolve()
    return relative.as_posix()


def _digest(paths: Iterable[Path]) -> str:
    files = list(paths)
    if not files:
        return ""
    hasher = hashlib.sha256()
    files.sort(key=_normalize_for_digest)
    for file_path in files:
        normalized_path = _normalize_for_digest(file_path)
        hasher.update(normalized_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(file_path.read_bytes())
    return hasher.hexdigest()


def _write_output(key: str, value: str) -> None:
    output_target = os.environ.get("GITHUB_OUTPUT")
    line = f"{key}={value}\n"
    if output_target:
        with Path(output_target).open("a", encoding="utf-8") as handle:
            handle.write(line)
    else:
        print(line, end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cache key components")
    parser.add_argument("--python", action="append", default=[], dest="python_paths", help="Python requirement or lock files")
    parser.add_argument("--node", action="append", default=[], dest="node_paths", help="Node pnpm lock files")
    args = parser.parse_args()

    python_hash = _digest(_existing_paths(args.python_paths))
    node_hash = _digest(_existing_paths(args.node_paths))

    _write_output("python-hash", python_hash)
    _write_output("node-hash", node_hash)


if __name__ == "__main__":
    main()
