#!/bin/bash
# vim: set ft=bash ts=2 sw=2:
# Install any Poetry plugins that the caller has requested, via pipx
set -e
export PIPX_HOME="$POETRY_HOME/venv"
export PIPX_BIN_DIR="$POETRY_HOME/bin"
if [ ! -z "$POETRY_PLUGINS" ]; then
  while IFS=',' read -ra PARSED; do
    for PLUGIN_NAME in "${PARSED[@]}"; do
      pipx inject poetry "$PLUGIN_NAME"
    done
  done <<< "$POETRY_PLUGINS"
fi
