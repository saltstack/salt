#!/bin/bash
################################################################################
#
# Title: Build Package Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This creates a macOS package for Salt from the contents of
#              ./build and signs it
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#       or
#     - Xcode
#
# Usage:
#     This script can be passed the following parameter:
#         $1 : <version> : the version name to give the package. Defaults to the
#                          git repo version
#
#     Example:
#         The following will build Salt version 3006.1-1 and stage all files in
#         the ./build directory relative to this script
#
#         ./package.sh 3006.1-1
#
# Environment Setup:
#
#     Import Certificates:
#         Import the Salt Developer Installer Signing certificate using the
#         following command:
#
#         security import "developerID_installer.p12" -k ~/Library/Keychains/login.keychain
#
#         NOTE: The .p12 certificate is required as the .cer certificate is
#               missing the private key. This can be created by exporting the
#               certificate from the machine it was created on
#
#     Define Environment Variables:
#         Create an environment variable with the name of the certificate to use
#         from the keychain for installer signing. Use the following command
#         (The actual value must match what is provided in the certificate):
#
#         export DEV_INSTALL_CERT="Developer ID Installer: Salt Stack, Inc. (AB123ABCD1)"
#
################################################################################
#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
# Get/Set Version
if [ "$1" == "" ]; then
    VERSION=$(git describe)
else
    VERSION=$1
fi

# Strip the v from the beginning
VERSION=${VERSION#"v"}

CPU_ARCH="$(uname -m)"
SRC_DIR="$(git rev-parse --show-toplevel)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
PKG_RESOURCES=$SRC_DIR/pkg/osx
CMD_OUTPUT=$(mktemp -t cmd.log)

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to build the Salt package:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help] [-v|--version]"
     echo ""
     echo "  -h, --help      this message"
     echo "  -v, --version   version of Salt display in the package"
     echo ""
     echo "  To build the Salt package:"
     echo "      example: $0 3006.1-1"
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
echo "Building Salt Package"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Make sure this is the Salt Repository
#-------------------------------------------------------------------------------
if [[ ! -e "$SRC_DIR/.git" ]] && [[ ! -e "$SRC_DIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the 'pkg/osx' directory of the Git checkout."
    exit 1
fi

#-------------------------------------------------------------------------------
# Add Title, Description, Version and CPU Arch to distribution.xml
#-------------------------------------------------------------------------------
DIST="$PKG_RESOURCES/distribution.xml"
if [ -f "$DIST" ]; then
    _msg "Removing existing distribution.xml"
    rm -f "$DIST"
    if ! [ -f "$DIST" ]; then
        _success
    else
        _failure
    fi
fi

_msg "Creating distribution.xml"
cp "$PKG_RESOURCES/distribution.xml.dist" "$DIST"
if [ -f "$DIST" ]; then
    _success
else
    CMD_OUTPUT="Failed to copy: $DIST"
    _failure
fi

# We need to do version first because Title contains version and we need to
# be able to check it
_msg "Setting package version"
SED_STR="s/@VERSION@/$VERSION/g"
sed -i "" "$SED_STR" "$DIST"
if grep -q "$VERSION" "$DIST"; then
    _success
else
    CMD_OUTPUT="Failed to set: $VERSION"
    _failure
fi

_msg "Setting package title"
TITLE="Salt $VERSION (Python 3)"
SED_STR="s/@TITLE@/$TITLE/g"
sed -i "" "$SED_STR" "$DIST"
if grep -q "$TITLE" "$DIST"; then
    _success
else
    CMD_OUTPUT="Failed to set: $TITLE"
    _failure
fi

_msg "Setting package description"
DESC="Salt $VERSION with Python 3"
SED_STR="s/@DESC@/$DESC/g"
sed -i "" "$SED_STR" "$DIST"
if grep -q "$DESC" "$DIST"; then
    _success
else
    CMD_OUTPUT="Failed to set: $DESC"
    _failure
fi

_msg "Setting package architecture"
SED_STR="s/@CPU_ARCH@/$CPU_ARCH/g"
sed -i "" "$SED_STR" "$DIST"
if grep -q "$CPU_ARCH" "$DIST"; then
    _success
else
    CMD_OUTPUT="Failed to set: $CPU_ARCH"
    _failure
fi

#-------------------------------------------------------------------------------
# Build and Sign the Package
#-------------------------------------------------------------------------------

_msg "Building the source package"
# Build the src package
FILE="salt-src-$VERSION-py3-$CPU_ARCH.pkg"
if pkgbuild --root="$BUILD_DIR" \
            --scripts=pkg-scripts \
            --identifier=com.saltstack.salt \
            --version="$VERSION" \
            --ownership=recommended \
            "$FILE" > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi


_msg "Building the product package (signed)"
FILE="salt-$VERSION-py3-$CPU_ARCH-signed.pkg"
if productbuild --resources=pkg-resources \
                --distribution=distribution.xml  \
                --package-path="salt-src-$VERSION-py3-$CPU_ARCH.pkg" \
                --version="$VERSION" \
                --sign "$DEV_INSTALL_CERT" \
                --timestamp \
                "$FILE" > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Building Salt Package Completed"
printf "=%.0s" {1..80}; printf "\n"
