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
SRC_DIR="$(git rev-parse --show-toplevel)"
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
     echo "  -h, --help             this message"
     echo "  -b, --build            build python instead of fetching"
     echo "  -v, --version          version of python to install, must be a"
     echo "                         version available in relenv"
     echo "  -r, --relenv-version   version of relenv to install"
     echo ""
     echo "  To build python 3.10.13 you need to use relenv 0.13.5:"
     echo "      example: $0 --relenv-version 0.13.5 --version 3.10.13"
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

function _parse_yaml {
   local prefix=$2
   local s='[[:space:]]*' w='[a-zA-Z0-9_]*' fs=$(echo @|tr @ '\034')
   sed -ne "s|^\($s\):|\1|" \
        -e "s|^\($s\)\($w\)$s:$s[\"']\(.*\)[\"']$s\$|\1$fs\2$fs\3|p" \
        -e "s|^\($s\)\($w\)$s:$s\(.*\)$s\$|\1$fs\2$fs\3|p"  $1 |
   awk -F$fs '{
      indent = length($1)/2;
      vname[indent] = $2;
      for (i in vname) {if (i > indent) {delete vname[i]}}
      if (length($3) > 0) {
         vn=""; for (i=0; i<indent; i++) {vn=(vn)(vname[i])("_")}
         printf("%s%s%s=\"%s\"\n", "'$prefix'",vn, $2, $3);
      }
   }'
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

# Get defaults from workflows. This defines $python_version and $relenv_version
eval "$(_parse_yaml "$SRC_DIR/cicd/shared-gh-workflows-context.yml")"

if [ -z "$PY_VERSION" ]; then
    PY_VERSION=$python_version
fi

if [ -z "$RELENV_VERSION" ]; then
    RELENV_VERSION=$relenv_version
fi

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
echo "- Relenv Version: $RELENV_VERSION"
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
    pip install relenv==${RELENV_VERSION}
else
    pip install relenv
fi
if [ -n "$(relenv --version)" ]; then
    _success
else
    _failure
fi
export RELENV_FETCH_VERSION=$(relenv --version)

#-------------------------------------------------------------------------------
# Building Python with Relenv
#-------------------------------------------------------------------------------
if [ $BUILD -gt 0 ]; then
    echo "- Building python (relenv):"
    relenv build --clean --python=$PY_VERSION
else
    # We want to suppress the output here so it looks nice
    # To see the output, remove the output redirection
    _msg "Fetching python (relenv)"
    relenv fetch --python=$PY_VERSION && _success || _failure
fi

_msg "Extracting python environment"
relenv create --python=$PY_VERSION "$BUILD_DIR/opt/salt"
if [ -f "$BLD_PY_BIN" ]; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Removing Unneeded Libraries from Python
#-------------------------------------------------------------------------------
PY_VERSION_MINOR=$($BLD_PY_BIN -c 'import sys; sys.stdout.write("{}.{}".format(*sys.version_info))')
REMOVE=(
    "idlelib"
    "test"
    "tkinter"
    "turtledemo"
)
for i in "${REMOVE[@]}"; do
    TEST_DIR="$BUILD_DIR/opt/salt/lib/python${PY_VERSION_MINOR}/$i"
    if [ -d "$TEST_DIR" ]; then
        _msg "Removing $i directory"
        rm -rf "$TEST_DIR" && _success || _failure
    fi
done

#-------------------------------------------------------------------------------
# Finished
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Build Python with Relenv Completed"
printf "=%.0s" {1..80}; printf "\n"
