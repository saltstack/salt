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
BUILD_DIR="$SCRIPT_DIR/build/opt/salt"
PIP_BIN="$BUILD_DIR/bin/pip3"
PYTHON_BIN="$BUILD_DIR/bin/python3"
PYTHON_VER="$($PYTHON_BIN -c 'import platform; print(platform.python_version())')"
PYTHON_DOT_VER=${PYTHON_VER%.*}
REQ_FILE="$SRC_DIR/requirements/static/pkg/py$PYTHON_DOT_VER/darwin.txt"

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
     echo "             [-h|--help]"
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
# Get Parameters
#-------------------------------------------------------------------------------
while true; do
    if [[ -z "$1" ]]; then break; fi
    case "$1" in
        -h | --help )
            _usage
            exit 0
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            exit 1
            ;;
        * )
            shift
            ;;
    esac
done

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Install Salt into Build Environment"
echo "Python Version: $PYTHON_DOT_VER"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
REMOVE_DIRS=(
    "$SRC_DIR/build"
    "$SRC_DIR/dist"
)
for dir in "${REMOVE_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        _msg "Removing $dir"
        rm -rf "$dir"
        if [ -d "$dir" ]; then
            _failure
        else
            _success
        fi
    fi
done

TEST_DIR="$SCRIPT_DIR/build/opt/salt/lib/python3.*/site-packages/salt*/"
if compgen -G "$TEST_DIR" > /dev/null; then
    _msg "Removing salt directory"
    find "$TEST_DIR" -type d -exec rm -rf {} +
    if ! compgen -G "$TEST_DIR" > /dev/null; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Install Requirements into the Python Environment
#-------------------------------------------------------------------------------
_msg "Installing Salt requirements"
$PIP_BIN install -r "$REQ_FILE" > /dev/null 2>&1
if [ -f "$BUILD_DIR/bin/distro" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Install Salt into the Python Environment
#-------------------------------------------------------------------------------
_msg "Installing Salt"
RELENV_PIP_DIR="yes" $PIP_BIN install "$SRC_DIR" > /dev/null 2>&1
TEST_DIR="$SCRIPT_DIR/build/opt/salt/lib/python3.*/site-packages/salt*"
if compgen -G "$TEST_DIR" > /dev/null; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Install Salt into Build Environment Completed"
printf "=%.0s" {1..80}; printf "\n"
