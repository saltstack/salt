#!/bin/bash
# vim: set ft=bash ts=2 sw=2:
# Configure Poetry

set -e

echo "Setting cache-dir=$POETRY_CACHE"
poetry config cache-dir "$POETRY_CACHE"

echo "Setting virtualenvs.create=true"
poetry config virtualenvs.create true

echo "Setting virtualenvs.in-project=true"
poetry config virtualenvs.in-project true

if [ ! -z "$MAX_WORKERS" ]; then
  echo "Setting MAX_WORKERS=$MAX_WORKERS"
  poetry config installer.max-workers "$MAX_WORKERS"
fi

if [ "$DISABLE_KEYRING" == "true" ]; then
  echo "Setting keyring.enabled=false"
  poetry config keyring.enabled false
fi

poetry config --list
