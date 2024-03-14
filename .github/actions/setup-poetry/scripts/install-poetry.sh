#!/bin/bash
# vim: set ft=bash ts=2 sw=2:
# Install the Poetry build tool using pipx

set -e

echo "POETRY_CONFIG_DIR=$POETRY_CONFIG_DIR"
echo "POETRY_HOME=$POETRY_HOME"
echo "POETRY_CACHE=$POETRY_CACHE"

export PIPX_HOME="$POETRY_HOME/venv"
export PIPX_BIN_DIR="$POETRY_HOME/bin"

$PYTHON_BIN -m pip install --user --upgrade pipx
pipx install "poetry==${POETRY_VERSION}"
