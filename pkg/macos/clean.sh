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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOVE_DIRS=(
    "$SCRIPT_DIR/relative-environment-for-python"
    "$HOME/.local/relenv"
    "$SCRIPT_DIR/build"
    "$SCRIPT_DIR/venv"
    "$SRC_DIR/build"
    "$SRC_DIR/dist"
)

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to clean the package directory and build environment:"
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
echo "Cleaning Build Environment"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Cleaning Environment
#-------------------------------------------------------------------------------
if [ -n "${VIRTUAL_ENV}" ]; then
    _msg "Deactivating virtual environment"
    deactivate
    if [ -z "${VIRTUAL_ENV}" ]; then
        _success
    else
        _failure
    fi
fi

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

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Cleaning Build Environment Complete"
printf "=%.0s" {1..80}; printf "\n"
