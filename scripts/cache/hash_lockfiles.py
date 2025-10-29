#!/usr/bin/env python3
"""Compute deterministic hashes for dependency lock files."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _normalized_path(path: Path) -> tuple[str, Path]:
    resolved = path.resolve()
    repo_root = Path(_REPOSITORY_ROOT).resolve()
    try:
        relative = resolved.relative_to(repo_root)
        normalized = relative.as_posix()
    except ValueError:
        normalized = resolved.as_posix()
    return normalized, resolved


def _existing_paths(raw_paths: Iterable[str]) -> list[Path]:
    resolved_paths: dict[Path, None] = {}
    missing_paths: dict[Path, None] = {}
    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        resolved = candidate.resolve(strict=False)
        if not resolved.exists() or not resolved.is_file():
            missing_paths.setdefault(candidate, None)
            continue
        resolved_paths.setdefault(resolved, None)
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Lockfile(s) not found: {missing}")
    return list(resolved_paths)


def _digest(paths: Iterable[Path]) -> str:
    files: list[tuple[str, Path]] = []
    for path in paths:
        normalized, resolved = _normalized_path(path)
        files.append((normalized, resolved))
    if not files:
        return ""
    files.sort(key=lambda item: item[0])
    hasher = hashlib.sha256()
    for normalized, resolved in files:
        hasher.update(normalized.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(resolved.read_bytes())
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
