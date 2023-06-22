#!/bin/bash
################################################################################
#
# Title: Prep the Salt environment for Packaging
#
# Description: This prepares the Salt environment for packaging by removing
#              unneeded files, staging configs and plist files, etc.
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#       or
#     - Xcode
#
# Usage:
#     This script takes no parameters:
#
#     Example:
#         The following will prepare the Salt environment for packaging:
#
#         ./prep_salt.sh
#
################################################################################

#-------------------------------------------------------------------------------
# Script Functions
#-------------------------------------------------------------------------------

# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to prep the Salt package:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help]"
     echo ""
     echo "  -h, --help       this message"
     echo "  -b, --build-dir  the location of the build directory"
     echo ""
     echo "  To build the Salt package:"
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
    echo "output >>>>>>"
    cat "$CMD_OUTPUT" 1>&2
    echo "<<<<<< output"
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
        -b | --build-dir )
            shift
            BUILD_DIR="$*"
            shift
            ;;
        -* )
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
# Script Variables
#-------------------------------------------------------------------------------
SRC_DIR="$(git rev-parse --show-toplevel)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -z "$BUILD_DIR" ]; then
    BUILD_DIR="$SCRIPT_DIR/build"
fi
CONF_DIR="$BUILD_DIR/etc/salt"
CMD_OUTPUT=$(mktemp -t cmd.log)

#-------------------------------------------------------------------------------
# Delete temporary files on exit
#-------------------------------------------------------------------------------
function finish {
    rm "$CMD_OUTPUT"
}
trap finish EXIT

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Prepping Salt Package"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Make sure this is the Salt Repository
#-------------------------------------------------------------------------------
if [[ ! -e "$SRC_DIR/.git" ]] && [[ ! -e "$SRC_DIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the 'pkg/macos' directory of the Git checkout."
    exit 1
fi

#-------------------------------------------------------------------------------
# Copy salt-config from Salt Repo to /opt/salt
#-------------------------------------------------------------------------------
SALT_DIR="$BUILD_DIR/opt/salt"
if ! [ -d "$SALT_DIR" ]; then
    # We only need this for relenv builds
    mkdir -p "$SALT_DIR"
fi
if ! [ -f "$SALT_DIR/salt-config.sh" ]; then
    _msg "Staging Salt config script"
    cp "$SCRIPT_DIR/scripts/salt-config.sh" "$SALT_DIR/"
    if [ -f "$SALT_DIR/salt-config.sh" ]; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Copy Service Definitions from Salt Repo to the Package Directory
#-------------------------------------------------------------------------------
if ! [ -d "$BUILD_DIR/Library/LaunchDaemons" ]; then
    _msg "Creating LaunchDaemons directory"
    mkdir -p "$BUILD_DIR/Library/LaunchDaemons"
    if [ -d "$BUILD_DIR/Library/LaunchDaemons" ]; then
        _success
    else
        _failure
    fi
fi

ITEMS=(
    "minion"
    "master"
    "syndic"
    "api"
)
for i in "${ITEMS[@]}"; do
    FILE="$BUILD_DIR/Library/LaunchDaemons/com.saltstack.salt.$i.plist"
    if ! [ -f "$FILE" ]; then
        _msg "Copying $i service definition"
        cp "$SCRIPT_DIR/scripts/com.saltstack.salt.$i.plist" "$FILE"
        if [ -f "$FILE" ]; then
            _success
        else
            _failure
        fi
    fi
done

#-------------------------------------------------------------------------------
# Remove unnecessary files from the package
#-------------------------------------------------------------------------------
ITEMS=(
    "pkgconfig"
    "share"
    "__pycache__"
)

for i in "${ITEMS[@]}"; do
    if [[ -n $(find "$BUILD_DIR" -name "$i" -type d) ]]; then
        _msg "Removing $i directories"
        find "$BUILD_DIR" -name "$i" -type d -prune -exec rm -rf {} \;
        if [[ -z $(find "$BUILD_DIR" -name "$i" -type d) ]]; then
            _success
        else
            _failure
        fi
    fi
done

if [[ -n $(find "$BUILD_DIR" -name "*.pyc" -type f) ]]; then
    _msg "Removing *.pyc files"
    find "$BUILD_DIR" -name "*.pyc" -type f -delete
    if [[ -z $(find "$BUILD_DIR" -name "*.pyc" -type f) ]]; then
        _success
    else
        _failure
    fi
fi

#-------------------------------------------------------------------------------
# Copy Config Files from Salt Repo to the Package Directory
#-------------------------------------------------------------------------------
if ! [ -d "$CONF_DIR" ]; then
    _msg "Creating config directory"
    mkdir -p "$CONF_DIR"
    if [ -d "$CONF_DIR" ]; then
        _success
    else
        _failure
    fi
fi
ITEMS=(
  "minion"
  "master"
)
for i in "${ITEMS[@]}"; do
    if ! [ -f "$CONF_DIR/$i.dist" ]; then
        _msg "Copying $i config"
        cp "$SRC_DIR/conf/$i" "$CONF_DIR/$i.dist"
        if [ -f "$CONF_DIR/$i.dist" ]; then
            _success
        else
            _failure
        fi
    fi
done

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Prepping Salt Package Completed"
printf "=%.0s" {1..80}; printf "\n"
