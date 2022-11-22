#!/bin/bash
################################################################################
# Title: Clean Environment Script
# Author: Twangboy
#
# Description: This script cleans up build artifacts from the package directory.
#              Run this script with the -h option for more information
################################################################################
#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
SRC_DIR="$(git rev-parse --show-toplevel)"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RELENV_SRC="$SCRIPT_DIR/relative-environment-for-python"
RELENV_DIR="$HOME/.local/relenv"
BUILD_DIR="$SCRIPT_DIR/build"

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to clean the package directory:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help]"
     echo ""
     echo "  -h, --help      this message"
     echo ""
     echo "  To clean the package directory:"
     echo "      example: $0"
}

# _msg
#
#   Prints the message with a dash... no new line
_msg() {
    printf -- "- %s: " "$1"
}

# _success
#
#   Prints a green Success
_success() {
    printf "\e[32m%s\e[0m\n" "Success"
}

# _failure
#
#   Prints a red Failure and exits
_failure() {
    printf "\e[31m%s\e[0m\n" "Failure"
    exit 1
}

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Cleaning Build Environment"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
if [ -d "$BUILD_DIR" ]; then
    _msg "Removing BuildDirectory"
    rm -rf "$BUILD_DIR"
    if [ -d "$BUILD_DIR" ]; then
        _failure
    else
        _success
    fi
fi

if [ -d "$RELENV_SRC" ]; then
    _msg "Removing Relenv Source Directory"
    rm -rf "$RELENV_SRC"
    if [ -d "$RELENV_SRC" ]; then
        _failure
    else
        _success
    fi
fi

if [ -d "$RELENV_DIR" ]; then
    _msg "Removing Relenv Build Directory"
    rm -rf "$RELENV_DIR"
    if ! [ -d "$RELENV_DIR" ]; then
        _success
    else
        _failure
    fi
fi

if [ -n "${VIRTUAL_ENV}" ]; then
    _msg "Deactivating Virtual Environment"
    deactivate
    if [ -z "${VIRTUAL_ENV}" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$SCRIPT_DIR/venv" ]; then
    _msg "Removing Virtual Environment Directory"
    rm -rf "$SCRIPT_DIR/venv"
    if ! [ -d "$SCRIPT_DIR/venv" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$SRC_DIR/build" ]; then
    _msg "Removing Build Directory"
    rm -rf "$SRC_DIR/build"
    if ! [ -d "$SRC_DIR/build" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$SRC_DIR/dist" ]; then
    _msg "Removing Dist Directory"
    rm -rf "$SRC_DIR/dist"
    if ! [ -d "$SRC_DIR/dist" ]; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Cleaning Build Environment Complete"
printf "=%.0s" {1..80}; printf "\n"
