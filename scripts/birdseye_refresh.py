"""Birdseye JSON を最新化するユーティリティ。"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Iterable as IterableABC
from pathlib import Path
from typing import Any, DefaultDict, Iterable, List, Sequence, Set, Tuple


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh Birdseye JSON metadata.")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs/birdseye"),
        help="Birdseye JSON が存在するディレクトリ",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="変更点を表示するがファイルは更新しない",
    )
    return parser.parse_args(argv)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _dump_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _serialize(data: Any) -> str:
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


def _build_edge_maps(edges: Iterable[Tuple[str, str]]) -> Tuple[DefaultDict[str, Set[str]], DefaultDict[str, Set[str]]]:
    outgoing: DefaultDict[str, Set[str]] = defaultdict(set)
    incoming: DefaultDict[str, Set[str]] = defaultdict(set)
    for source, target in edges:
        outgoing[source].add(target)
        incoming[target].add(source)
    return outgoing, incoming


def _normalize_edges(raw_edges: Iterable[Any]) -> List[Tuple[str, str]]:
    normalized: List[Tuple[str, str]] = []
    for item in raw_edges:
        pair: Tuple[Any, ...] | None
        if isinstance(item, (list, tuple)):
            pair = tuple(item)
        elif isinstance(item, IterableABC) and not isinstance(item, (str, bytes)):
            pair = tuple(item)
        else:
            pair = None
        if pair is None or len(pair) != 2:
            continue
        source, target = pair
        normalized.append((str(source), str(target)))
    return normalized


def _apply_if_changed(path: Path, before: str, data: Any, dry_run: bool, changed: List[Path]) -> None:
    after = _serialize(data)
    if before == after:
        return
    if dry_run:
        print(f"[DRY-RUN] {path}")
    else:
        _dump_json(path, data)
        print(f"Updated {path}")
    changed.append(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    docs_dir: Path = args.docs_dir
    dry_run: bool = args.dry_run

    changed: List[Path] = []

    index_path = docs_dir / "index.json"
    index_data = _load_json(index_path)
    index_before = _serialize(index_data)
    edges = _normalize_edges(index_data.get("edges", []))

    outgoing, incoming = _build_edge_maps(edges)

    caps_dir = docs_dir / "caps"
    cap_entries: List[Tuple[Path, Any, str]] = []
    for cap_path in sorted(caps_dir.glob("*.json")):
        cap_data = _load_json(cap_path)
        cap_before = _serialize(cap_data)
        node_id = str(cap_data.get("id", ""))
        cap_data["deps_out"] = sorted(outgoing.get(node_id, set()))
        cap_data["deps_in"] = sorted(incoming.get(node_id, set()))
        cap_entries.append((cap_path, cap_data, cap_before))

    hot_path = docs_dir / "hot.json"
    hot_data = _load_json(hot_path)
    hot_before = _serialize(hot_data)

    targets: List[Tuple[Path, Any, str]] = [
        (index_path, index_data, index_before),
        *cap_entries,
        (hot_path, hot_data, hot_before),
    ]

    for path, data, before in targets:
        _apply_if_changed(path, before, data, dry_run, changed)

    action = "would change" if dry_run else "updated"
    print(f"{len(changed)} file(s) {action}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
