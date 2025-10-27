#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'USAGE'
Usage: scripts/sync_chainlit_subtree.sh --prefix <path> --repo <repository> --tag <tag> [--remote <remote>] [--dry-run]

必須引数:
  --prefix  サブツリーをマウントするディレクトリ（例: core_ext/chainlit）
  --repo    取得元のリポジトリ URL またはリモート名
  --tag     取り込み対象のタグ名
任意引数:
  --remote  fetch 時に利用するリモート名（省略時は --repo の値を使用）
  --dry-run 実際の git コマンドを実行せず、実行予定のコマンドを表示
USAGE
}

PREFIX=""
REPO=""
TAG=""
REMOTE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --repo)
            REPO="$2"
            shift 2
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --remote)
            REMOTE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift 1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ -z "$PREFIX" || -z "$REPO" || -z "$TAG" ]]; then
    echo "Missing required arguments" >&2
    usage >&2
    exit 1
fi

GIT_BIN="${GIT_BIN:-git}"
FETCH_SOURCE="$REPO"
if [[ -n "$REMOTE" ]]; then
    FETCH_SOURCE="$REMOTE"
fi

FETCH_CMD=("$GIT_BIN" "fetch" "$FETCH_SOURCE" "refs/tags/$TAG:refs/tags/$TAG")
PULL_CMD=("$GIT_BIN" "subtree" "pull" "--prefix" "$PREFIX" "$FETCH_SOURCE" "$TAG")

if [[ $DRY_RUN -eq 1 ]]; then
    printf "[DRY-RUN] %s\n" "${FETCH_CMD[*]}"
    printf "[DRY-RUN] %s\n" "${PULL_CMD[*]}"
    exit 0
fi

"${FETCH_CMD[@]}"
"${PULL_CMD[@]}"
