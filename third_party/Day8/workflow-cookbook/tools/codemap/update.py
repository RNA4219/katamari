"""Birdseye codemap の再生成スクリプト。"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence


SUPPORTED_SUFFIXES = {".md", ".py"}
OUTPUT_DIR = Path("docs") / "birdseye"
CAPS_DIR_NAME = "caps"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass(frozen=True)
class UpdateOptions:
    targets: tuple[Path, ...]
    emit: str


@dataclass
class Capsule:
    identifier: str
    path: Path
    role: str
    summary: str
    public_api: list[str]
    tests: list[str]
    risks: list[str]
    mtime: datetime
    deps_out: set[str] = field(default_factory=set)
    deps_in: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Codemap:
    nodes: dict[str, Capsule]
    edges: list[tuple[str, str]]


def parse_args(argv: Iterable[str] | None = None) -> UpdateOptions:
    parser = argparse.ArgumentParser(
        description="Regenerate Birdseye index and capsules.",
    )
    parser.add_argument(
        "--targets",
        type=str,
        required=True,
        help="Comma-separated list of directories or files to analyse.",
    )
    parser.add_argument(
        "--emit",
        type=str,
        choices=("index", "caps", "index+caps"),
        default="index+caps",
        help="Select which artefacts to write.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    target_paths = tuple(Path(value.strip()) for value in args.targets.split(",") if value.strip())
    if not target_paths:
        parser.error("--targets must contain at least one path")
    return UpdateOptions(targets=target_paths, emit=args.emit)


def run_update(options: UpdateOptions) -> None:
    root = Path.cwd().resolve()
    output_dir = (root / OUTPUT_DIR).resolve()
    caps_dir = output_dir / CAPS_DIR_NAME
    caps_dir.mkdir(parents=True, exist_ok=True)

    codemap = generate_codemap(root, options.targets)

    generated_at_dt = datetime.now(timezone.utc).replace(microsecond=0)
    generated_at = _format_timestamp(generated_at_dt)
    latest_mtime_dt = max((capsule.mtime for capsule in codemap.nodes.values()), default=generated_at_dt)
    latest_mtime = _format_timestamp(latest_mtime_dt)

    if options.emit in {"index", "index+caps"}:
        index_path = output_dir / "index.json"
        index_data = {
            "generated_at": generated_at,
            "nodes": {
                identifier: {
                    "role": capsule.role,
                    "caps": str(_capsule_path_for(identifier)),
                    "mtime": _format_timestamp(capsule.mtime),
                }
                for identifier, capsule in sorted(codemap.nodes.items())
            },
            "edges": [[source, target] for source, target in codemap.edges],
            "mtime": latest_mtime,
        }
        _dump_json(index_path, index_data)

    if options.emit in {"caps", "index+caps"}:
        for identifier, capsule in sorted(codemap.nodes.items()):
            capsule_path = root / _capsule_path_for(identifier)
            capsule_data = {
                "id": identifier,
                "role": capsule.role,
                "summary": capsule.summary,
                "public_api": capsule.public_api,
                "tests": capsule.tests,
                "risks": capsule.risks,
                "deps_out": sorted(capsule.deps_out),
                "deps_in": sorted(capsule.deps_in),
                "generated_at": generated_at,
                "mtime": _format_timestamp(capsule.mtime),
            }
            _dump_json(capsule_path, capsule_data)


def generate_codemap(root: Path, targets: Sequence[Path]) -> Codemap:
    resolved_targets = _resolve_targets(root, targets)
    analysis_roots = _analysis_roots(resolved_targets)
    nodes, module_map = _build_capsules(root, resolved_targets, analysis_roots)
    _populate_dependencies(root, nodes, module_map)
    seeds = _collect_seed_identifiers(root, nodes, resolved_targets)
    selected = _expand_neighbourhood(nodes, seeds, hops=2)
    selected_nodes = {
        identifier: Capsule(
            identifier=capsule.identifier,
            path=capsule.path,
            role=capsule.role,
            summary=capsule.summary,
            public_api=list(capsule.public_api),
            tests=list(capsule.tests),
            risks=list(capsule.risks),
            mtime=capsule.mtime,
            deps_out={dep for dep in capsule.deps_out if dep in selected},
            deps_in={dep for dep in capsule.deps_in if dep in selected},
        )
        for identifier, capsule in nodes.items()
        if identifier in selected
    }
    edges = [
        (source, target)
        for source, capsule in sorted(selected_nodes.items())
        for target in sorted(capsule.deps_out)
    ]
    return Codemap(nodes=selected_nodes, edges=edges)


def _resolve_targets(root: Path, targets: Sequence[Path]) -> list[Path]:
    seen: set[Path] = set()
    resolved: list[Path] = []
    for target in targets:
        candidate = target if target.is_absolute() else root / target
        if not candidate.exists():
            raise FileNotFoundError(f"Target '{target}' does not exist")
        resolved_path = candidate.resolve()
        if resolved_path in seen:
            continue
        seen.add(resolved_path)
        resolved.append(resolved_path)
    return resolved


def _analysis_roots(targets: Sequence[Path]) -> list[Path]:
    roots: set[Path] = set()
    for target in targets:
        roots.add(target if target.is_dir() else target.parent)
    return sorted(roots, key=lambda path: path.as_posix())


def _build_capsules(
    root: Path,
    targets: Sequence[Path],
    analysis_roots: Sequence[Path],
) -> tuple[dict[str, Capsule], dict[str, str]]:
    output_dir = (root / OUTPUT_DIR).resolve()
    discovered: set[Path] = {
        path.resolve()
        for base in analysis_roots
        for path in _iter_source_files(base, output_dir)
    }
    for target in targets:
        if target.is_file() and _should_include(target, output_dir):
            discovered.add(target.resolve())
    files = sorted(discovered, key=lambda path: path.relative_to(root).as_posix())

    nodes: dict[str, Capsule] = {}
    module_map: dict[str, str] = {}

    for path in files:
        identifier = path.relative_to(root).as_posix()
        role, summary, public_api = _summarize_file(path)
        capsule = Capsule(
            identifier=identifier,
            path=path,
            role=role,
            summary=summary,
            public_api=public_api,
            tests=[],
            risks=[],
            mtime=_file_mtime(path),
        )
        nodes[identifier] = capsule
        if path.suffix.lower() == ".py":
            module_name = _module_name_for_path(path, root)
            if module_name:
                module_map[module_name] = identifier
                alias = _alias_module_name(module_name)
                if alias and alias not in module_map:
                    module_map[alias] = identifier
    return nodes, module_map


def _collect_seed_identifiers(
    root: Path,
    nodes: Mapping[str, Capsule],
    targets: Sequence[Path],
) -> set[str]:
    seeds: set[str] = set()
    for target in targets:
        if target.is_dir():
            for identifier, capsule in nodes.items():
                try:
                    capsule.path.relative_to(target)
                except ValueError:
                    continue
                seeds.add(identifier)
        else:
            try:
                identifier = target.relative_to(root).as_posix()
            except ValueError:
                continue
            if identifier in nodes:
                seeds.add(identifier)
    return seeds


def _expand_neighbourhood(
    nodes: Mapping[str, Capsule],
    seeds: set[str],
    *,
    hops: int,
) -> set[str]:
    if not seeds:
        return set()
    adjacency = {
        identifier: set(capsule.deps_out) | set(capsule.deps_in)
        for identifier, capsule in nodes.items()
    }
    visited = set(seeds)
    queue = deque((seed, 0) for seed in seeds)
    while queue:
        current, depth = queue.popleft()
        if depth >= hops:
            continue
        for neighbour in adjacency.get(current, set()):
            if neighbour not in nodes or neighbour in visited:
                continue
            visited.add(neighbour)
            queue.append((neighbour, depth + 1))
    return visited


def _populate_dependencies(root: Path, nodes: dict[str, Capsule], module_map: Mapping[str, str]) -> None:
    for capsule in nodes.values():
        if capsule.path.suffix.lower() == ".md":
            dependencies = _extract_markdown_dependencies(capsule.path, root)
        else:
            dependencies = _extract_python_dependencies(capsule.path, root, module_map)
        filtered = {dep for dep in dependencies if dep in nodes and dep != capsule.identifier}
        capsule.deps_out = filtered

    for source, capsule in nodes.items():
        for target in capsule.deps_out:
            nodes[target].deps_in.add(source)


def _iter_source_files(target: Path, output_dir: Path) -> Iterator[Path]:
    if target.is_dir():
        for path in target.rglob("*"):
            if path.is_file() and _should_include(path, output_dir):
                yield path
    elif target.is_file():
        if _should_include(target, output_dir):
            yield target
    else:
        raise FileNotFoundError(f"Target '{target}' does not exist")


def _should_include(path: Path, output_dir: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        return False
    try:
        return output_dir not in path.resolve().parents
    except OSError:
        return False


def _summarize_file(path: Path) -> tuple[str, str, list[str]]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return "markdown", _summarize_markdown(path), []
    summary, public_api = _summarize_python(path)
    return "python", summary, public_api


def _summarize_markdown(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if heading:
                return heading
        else:
            return stripped
    return ""


def _summarize_python(path: Path) -> tuple[str, list[str]]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "", []
    try:
        module = ast.parse(source)
    except SyntaxError:
        return "", []

    explicit = _extract_explicit_all(module)
    if explicit is not None:
        public_api = explicit
    else:
        public_api = _infer_public_api(module)
    summary = _derive_python_summary(module, source, public_api)
    return summary, public_api


def _derive_python_summary(module: ast.Module, source: str, public_api: Sequence[str]) -> str:
    module_doc = ast.get_docstring(module)
    if module_doc:
        summary = _first_summary_line(module_doc)
        if summary:
            return summary

    exported_doc = _docstring_from_public_api(module, public_api)
    if exported_doc:
        return exported_doc

    public_doc = _first_public_docstring(module)
    if public_doc:
        return public_doc

    comment = _first_comment_line(source)
    if comment:
        return comment

    return ""


def _first_summary_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _docstring_from_public_api(module: ast.Module, public_api: Sequence[str]) -> str:
    if not public_api:
        return ""

    definitions: dict[str, ast.AST] = {}
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions.setdefault(node.name, node)

    for name in public_api:
        node = definitions.get(name)
        if node is None:
            continue
        doc = ast.get_docstring(node)
        if not doc:
            continue
        summary = _first_summary_line(doc)
        if summary:
            return summary
    return ""


def _first_public_docstring(module: ast.Module) -> str:
    fallback = ""
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
            doc = ast.get_docstring(node)
            if doc:
                summary = _first_summary_line(doc)
                if summary:
                    return summary
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc and not fallback:
                summary = _first_summary_line(doc)
                if summary:
                    fallback = summary
    return fallback


def _first_comment_line(source: str) -> str:
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#!"):
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if not text:
                continue
            if text.lower().startswith("coding") or text.lower().startswith("-*- coding"):
                continue
            return text
    return ""


def _extract_explicit_all(module: ast.Module) -> list[str] | None:
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    value = node.value
                    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                        names = [
                            elt.value
                            for elt in value.elts
                            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                        ]
                        return sorted(dict.fromkeys(names))
    return None


def _infer_public_api(module: ast.Module) -> list[str]:
    exports: list[str] = []
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    exports.append(target.id)
    return sorted(dict.fromkeys(exports))


def _extract_markdown_dependencies(path: Path, root: Path) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    dependencies: set[str] = set()
    for match in MARKDOWN_LINK.finditer(text):
        raw = match.group(1).strip()
        if not raw or raw.startswith("#"):
            continue
        if "://" in raw or raw.startswith("mailto:"):
            continue
        cleaned = raw.split("#", 1)[0]
        if not cleaned:
            continue
        candidate = (path.parent / cleaned).resolve()
        if not candidate.exists() or candidate.is_dir():
            continue
        if candidate.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        try:
            rel = candidate.relative_to(root)
        except ValueError:
            continue
        dependencies.add(rel.as_posix())
    return dependencies


def _extract_python_dependencies(path: Path, root: Path, module_map: Mapping[str, str]) -> set[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    try:
        module = ast.parse(source)
    except SyntaxError:
        return set()

    current_module = _module_name_for_path(path, root)
    dependencies: set[str] = set()

    for node in module.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                dependencies.update(_resolve_module(alias.name, module_map))
        elif isinstance(node, ast.ImportFrom):
            modules = _modules_from_import_from(node, current_module)
            for module_name in modules:
                dependencies.update(_resolve_module(module_name, module_map))
    return dependencies


def _modules_from_import_from(node: ast.ImportFrom, current_module: str) -> list[str]:
    modules: list[str] = []
    if node.level == 0:
        base = node.module or ""
        if base:
            modules.append(base)
        for alias in node.names:
            if alias.name == "*":
                continue
            modules.append(f"{base}.{alias.name}" if base else alias.name)
        return modules

    base = _resolve_relative_module(current_module, node.module, node.level)
    if base:
        modules.append(base)
    for alias in node.names:
        if alias.name == "*" or not base:
            continue
        modules.append(f"{base}.{alias.name}")
    return modules


def _resolve_relative_module(current_module: str, module: str | None, level: int) -> str:
    parts = [part for part in current_module.split(".") if part]
    if level > len(parts):
        prefix: list[str] = []
    else:
        prefix = parts[: len(parts) - level]
    if module:
        prefix.extend(part for part in module.split(".") if part)
    return ".".join(prefix)


def _resolve_module(module_name: str, module_map: Mapping[str, str]) -> set[str]:
    parts = module_name.split(".")
    while parts:
        candidate = ".".join(parts)
        target = module_map.get(candidate)
        if target is not None:
            return {target}
        parts.pop()
    return set()


def _alias_module_name(module_name: str) -> str | None:
    parts = module_name.split(".")
    if len(parts) > 1 and parts[0] == "src":
        return ".".join(parts[1:])
    return None


def _module_name_for_path(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _file_mtime(path: Path) -> datetime:
    try:
        stat = path.stat()
    except OSError:
        return datetime.fromtimestamp(0, timezone.utc)
    return datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0)


def _capsule_path_for(identifier: str) -> Path:
    stem = ".".join(Path(identifier).with_suffix("").parts)
    return OUTPUT_DIR / CAPS_DIR_NAME / f"{stem}.json"


def _dump_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv: Iterable[str] | None = None) -> int:
    options = parse_args(argv)
    run_update(options)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
