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
PY_VERSION="3.10.7"

# Valid versions supported by MacOS
PY_VERSIONS=(
    "3.10.7"
    "3.9.15"
    "3.9.14"
    "3.9.13"
    "3.9.12"
    "3.9.11"
    "3.8.15"
    "3.8.14"
    "3.8.13"
    "3.8.12"
    "3.8.11"
)

# Locations
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYS_PY_BIN="$(which python3)"
RELENV_SRC="$SCRIPT_DIR/relative-environment-for-python"
RELENV_URL="https://github.com/saltstack/relative-environment-for-python"
RELENV_BLD="$HOME/.local/relenv/build"
BUILD_DIR="$SCRIPT_DIR/build"
BLD_PY_BIN="$BUILD_DIR/opt/salt/bin/python3"

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
     echo "  -v, --version   version of python to install"
     echo "                  python version must be one of:"
     for i in "${PY_VERSIONS[@]}"; do
         echo "                  - $i"
     done
     echo ""
     echo "  To build python 3.9.15:"
     echo "      example: $0 --version 3.9.15"
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
            PY_VERSION="$*"
            shift
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            ;;
        * )
            PY_VERSION="$*"
            shift
            ;;
    esac
done

if ! [[ " ${PY_VERSIONS[*]} " =~ " $PY_VERSION " ]]; then
    echo "Invalid Python Version: $PY_VERSION"
    echo ""
    _usage
    exit 1
fi

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Build Python with Relenv"
echo "- Python Version: $PY_VERSION"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
if [ -d "$RELENV_SRC" ]; then
    _msg "Removing relenv source directory"
    rm -rf "$RELENV_SRC"
    if [ -d "$RELENV_SRC" ]; then
        _failure
    else
        _success
    fi
fi

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

#-------------------------------------------------------------------------------
# Cloning Relenv
#-------------------------------------------------------------------------------
#_msg "Cloning relenv"
#git clone --depth 1 "$RELENV_URL" "$RELENV_SRC" >/dev/null 2>&1
#if [ -d "$RELENV_SRC/relenv" ]; then
#    _success
#else
#    _failure
#fi

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
#pip install -e "$RELENV_SRC/." >/dev/null 2>&1
pip install relenv >/dev/null 2>&1
if [ -n "$(pip show relenv)" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Building Python with Relenv
#-------------------------------------------------------------------------------
_msg "Building python with relenv"
# We want to suppress the output here so it looks nice
# To see the output, remove the output redirection
python -m relenv build --clean >/dev/null 2>&1
if [ -f "$RELENV_BLD/x86_64-macos.tar.xz" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Moving Python to Build Directory
#-------------------------------------------------------------------------------
if ! [ -d "$BUILD_DIR/opt/salt" ]; then
    _msg "Creating build directory"
    mkdir -p "$BUILD_DIR/opt/salt"
    if [ -d "$BUILD_DIR/opt/salt" ]; then
        _success
    else
        _failure
    fi
fi

_msg "Moving python to build directory"
mv "$RELENV_BLD"/x86_64-macos/* "$BUILD_DIR/opt/salt/"
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
    if compgen -G "$TEST_DIR" > /dev/null; then
        _msg "Removing $i directory"
        find "$TEST_DIR" -type d -exec rm -rf {} +
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
