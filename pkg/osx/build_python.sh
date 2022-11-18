#!/bin/bash

################################################################################
# Make sure the script is launched with sudo
################################################################################
#if [[ $(id -u) -ne 0 ]]; then
#    echo ">>>>>> Re-launching as sudo <<<<<<"
#    exec sudo -E /bin/bash -c "$(printf '%q ' "$BASH_SOURCE" "$@")"
#fi

################################################################################
# Variables
################################################################################
# The default version to be built
PYTHON_VERSION="3.9.15"

# Valid versions supported by MacOS
PYTHON_VERSIONS=(
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

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
RELENV_DIR="$SCRIPT_DIR\relative-environment-for-python"
RELENV_URL="https://github.com/saltstack/relative-environment-for-python"
# TODO: python3 instead of python for OSX
PYTHON_BIN=$(which python)

################################################################################
# Functions
################################################################################
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
     for i in "${PYTHON_VERSIONS[@]}"; do
         echo "                  - $i"
     done
     echo ""
     echo "  build python 3.9.15"
     echo "      example: $0 --version 3.9.15"
}

_msg() {
    printf -- "- $1: "
}

_success() {
    printf '\e[32m%s\e[0m\n' "Success"
}

_failure() {
    printf '\e[31m%s\e[0m\n' "Failure"
    exit 1
}


################################################################################
# Get Parameters
################################################################################
while true; do
    if [[ -z "$1" ]]; then break; fi
    case "$1" in
        -h | --help )
            _usage
            exit 0
            ;;
        -v | --version )
            shift
            PYTHON_VERSION="$*"
            shift
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            ;;
        * )
            PYTHON_VERSION="$*"
            shift
            ;;
    esac
done

if ! [[ " ${PYTHON_VERSIONS[*]} " =~ " $PYTHON_VERSION " ]]; then
    echo "Invalid Python Version: $PYTHON_VERSION"
    echo ""
    _usage
    exit 1
fi

printf "=%.0s" {1..80}; printf "\n"
echo "Build Python with Relenv"
echo "- Python Version: $PYTHON_VERSION"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Prepping Environment
#-------------------------------------------------------------------------------
if [ -d "$RELENV_DIR" ]; then
    _msg "Removing Relenv Directory"
    rm -rf $RELENV_DIR
    if [ -d "$RELENV_DIR" ]; then
        _failure
    else
        _success
    fi
fi

if [ -n "${VIRTUAL_ENV}" ]; then
    _msg "Deactivating venv"
    if [ -z "${VIRTUAL_ENV}" ]; then
        _success
    else
        _failure
    fi
fi

if [ -d "$SCRIPT_DIR/venv" ]; then
    _msg "Removing venv dir"
    rm -rf "$SCRIPT_DIR/venv"
    if [ -d "$RELENV_DIR" ]; then
        _failure
    else
        _success
    fi
fi

#-------------------------------------------------------------------------------
# Downloading Relenv
#-------------------------------------------------------------------------------
_msg "Cloning Relenv"
git clone "--depth" 1 "$RELENV_URL" "$RELENV_DIR" >/dev/null 2>&1
if [ -d "$RELENV_DIR/relenv" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Setting up venv
#-------------------------------------------------------------------------------
_msg "Setting up venv"
$PYTHON_BIN -m venv "$SCRIPT_DIR/venv"
if [ -d "$SCRIPT_DIR/venv" ]; then
    _success
else
    _failure
fi

_msg "Activating venv"
# TODO: bin instead of scripts for OSX
source "$SCRIPT_DIR/venv/Scripts/activate"
if [ -n "${VIRTUAL_ENV}" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Setting up venv
#-------------------------------------------------------------------------------
_msg "Installing relenv"
pip install -e "$RELENV_DIR/." >/dev/null 2>&1
if [ -n "$(pip show relenv)" ]; then
    _success
else
    _failure
fi

_msg "Building Python with relenv"
python -m relenv build --clean
