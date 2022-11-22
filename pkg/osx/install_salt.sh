#!/bin/bash
################################################################################
#
# Title: Install Salt
# Author: Twangboy
#
# Description: This script installs Salt into the Python environment for
#              packaging. Checkout the version of Salt you want to install.
#              Then run this script. For more information, run this script with
#              the -h option.
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
SRC_DIR="$(git rev-parse --show-toplevel)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$SCRIPT_DIR/build/opt/salt/bin/python3"
# This gets used by relenv to place binaries in the salt root instead of in the
# bin directory
RELENV_PIP_DIR="yes"

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to install Salt into the Python environment:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help] [-v|--version]"
     echo ""
     echo "  -h, --help      this message"
     echo ""
     echo "  Install Salt:"
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
echo "Install Salt into Build Environment"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
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

TEST_DIR="$SCRIPT_DIR/build/opt/salt/lib/python3.*/site-packages/salt*/"
if compgen -G "$TEST_DIR" > /dev/null; then
    _msg "Removing Salt Directory"
    find "$TEST_DIR" -type d -exec rm -rf {} +
    if ! compgen -G "$TEST_DIR" > /dev/null; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Install Salt into the Python Environment
#-------------------------------------------------------------------------------
#_msg "Building Salt"
#$PYTHON_BIN "$SRC_DIR/setup.py" build -e "$PYTHON_BIN -E -s --upgrade" >/dev/null 2>&1
#TEST_DIR="$SRC_DIR/build/scripts-3*/salt-minion"
#if compgen -G "$TEST_DIR" > /dev/null; then
#    _success
#else
#    _failure
#fi

_msg "Installing Salt"
$PYTHON_BIN "$SRC_DIR/setup.py" install >/dev/null 2>&1
TEST_DIR="$SCRIPT_DIR/build/opt/salt/lib/python3.*/site-packages/salt*"
if compgen -G "$TEST_DIR" > /dev/null; then
    _success
else
    _failure
fi

printf -- "-%.0s" {1..80}; printf "\n"
echo "Install Salt into Build Environment Completed"
printf "=%.0s" {1..80}; printf "\n"
