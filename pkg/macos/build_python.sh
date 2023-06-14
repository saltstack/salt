#!/bin/bash
################################################################################
#
# Title: Build Python
# Author: Twangboy
#
# Description: This script builds Python from source using the Relative
#              Environment for Python project (relenv):
#
#              https://github.com/saltstack/relative-environment-for-python
#
#              The build is placed in the ./build directory relative to this
#              script.
#
#              For more information, run this script with the -h option.
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
# The default version to be built
# TODO: The is not selectable via RELENV yet. This has to match whatever relenv
# TODO: is building

# Locations
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYS_PY_BIN="$(which python3)"
BUILD_DIR="$SCRIPT_DIR/build"
BLD_PY_BIN="$BUILD_DIR/opt/salt/bin/python3"
RELENV_DIR="$HOME/.local/relenv"
BUILD=0

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to build Python using the Relenv library:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help] [-v|--version]"
     echo ""
     echo "  -h, --help      this message"
     echo "  -b, --build     build python instead of fetching"
     echo "  -v, --version   version of python to install, must be available with relenv"
     echo "  -r, --relenv-version   version of python to install, must be available with relenv"
     echo ""
     echo "  To build python 3.10.11:"
     echo "      example: $0 --version 3.10.11"
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
    printf '\e[32m%s\e[0m\n' "Success"
}

# _failure
#
#   Prints a red Failure and exits
_failure() {
    printf '\e[31m%s\e[0m\n' "Failure"
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
        -v | --version )
            shift
            PY_VERSION="$1"
            shift
            ;;
        -r | --relenv-version )
            shift
            RELENV_VERSION="$1"
            shift
            ;;
        -b | --build )
            BUILD=1
            shift
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            exit 1
            ;;
        * )
            echo "Invalid Arguments: $*"
            _usage
            exit 1
            ;;
    esac
done

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
if [ $BUILD -gt 0 ]; then
    echo "Build Python with Relenv"
else
    echo "Fetch Python with Relenv"
fi
echo "- Python Version: $PY_VERSION"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
if [ -d "$BUILD_DIR" ]; then
    _msg "Removing build directory"
    rm -rf "$BUILD_DIR"
    if ! [ -d "$BUILD_DIR" ]; then
        _success
    else
        _failure
    fi
fi

if [ -n "${VIRTUAL_ENV}" ]; then
    _msg "Deactivating virtual environment"
    deactivate
    if [ -z "${VIRTUAL_ENV}" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$SCRIPT_DIR/venv" ]; then
    _msg "Removing virtual environment directory"
    rm -rf "$SCRIPT_DIR/venv"
    if ! [ -d "$SCRIPT_DIR/venv" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$RELENV_DIR" ]; then
    _msg "Removing relenv directory"
    rm -rf "$RELENV_DIR"
    if ! [ -d "$RELENV_DIR" ]; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Setting Up Virtual Environment
#-------------------------------------------------------------------------------
_msg "Setting up virtual environment"
$SYS_PY_BIN -m venv "$SCRIPT_DIR/venv"
if [ -d "$SCRIPT_DIR/venv" ]; then
    _success
else
    _failure
fi

_msg "Activating virtual environment"
source "$SCRIPT_DIR/venv/bin/activate"
if [ -n "${VIRTUAL_ENV}" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Installing Relenv
#-------------------------------------------------------------------------------
_msg "Installing relenv"
if [ -n "${RELENV_VERSION}" ]; then
    pip install relenv==${RELENV_VERSION} >/dev/null 2>&1
    export RELENV_FETCH_VERSION=${RELENV_VERSION}
else
    pip install relenv >/dev/null 2>&1
fi
if [ -n "$(relenv --version)" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Building Python with Relenv
#-------------------------------------------------------------------------------
if [ $BUILD -gt 0 ]; then
    echo "- Building python (relenv):"
    relenv build --clean
else
    # We want to suppress the output here so it looks nice
    # To see the output, remove the output redirection
    _msg "Fetching python (relenv)"
    relenv fetch --python $PY_VERSION >/dev/null 2>&1
    if [ -f "$RELENV_DIR/build/$PY_VERSION-x86_64-macos.tar.xz" ]; then
        _success
    else
        _failure
    fi
fi

_msg "Extracting python environment"
relenv create "$BUILD_DIR/opt/salt"
if [ -f "$BLD_PY_BIN" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Removing Unneeded Libraries from Python
#-------------------------------------------------------------------------------
REMOVE=(
    "idlelib"
    "test"
    "tkinter"
    "turtledemo"
)
for i in "${REMOVE[@]}"; do
    TEST_DIR="$BUILD_DIR/opt/salt/lib/python3.*/$i"
    DIR=$(compgen -G "$TEST_DIR")
    if [ -n "$DIR" ]; then
        _msg "Removing $i directory"
        rm -rf "$DIR"
        if ! compgen -G "$TEST_DIR" > /dev/null; then
            _success
        else
            _failure
        fi
    fi
done

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Build Python with Relenv Completed"
printf "=%.0s" {1..80}; printf "\n"
