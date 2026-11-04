#!/usr/bin/env bash
# SubEmbed Launcher
# Robustly resolves canonical script location even when invoked via symlink.

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
PROJECT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

PYTHONPATH="$PROJECT_DIR:$PYTHONPATH" exec python3 -m subembed.cli "$@"
