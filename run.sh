#!/usr/bin/env bash
# SubEmbed Launcher
# Automatically detects arguments: opens GUI if no args, or CLI if video argument is passed.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="$DIR:$PYTHONPATH" exec python3 -m subembed.cli "$@"
