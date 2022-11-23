#!/bin/bash
################################################################################
#
# Title: Build Package Script for MacOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This creates a MacOS package for Salt from the contents of
#              ./build and signs it
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#       or
#     - Xcode
#
# Usage:
#     This script can be passed 2 parameters
#         $1 : <version> : the version name to give the package. Defaults to the
#                          git repo version
#
#     Example:
#         The following will build Salt version 3006.1-1 and stage all files in
#         the ./build directory relative to this script
#
#         ./build_pkg.sh 3006.1-1
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

CPU_ARCH=$(uname -m)
SRC_DIR=$(git rev-parse --show-toplevel)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUILD_DIR="$SCRIPT_DIR/build"
CONF_DIR="$BUILD_DIR/etc/salt"
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
     echo "             [-h|--help]"
     echo ""
     echo "  -h, --help      this message"
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
    echo "The MacOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the 'pkg/osx' directory of the Git checkout."
    exit 1
fi

#-------------------------------------------------------------------------------
# Copy Start Scripts from Salt Repo to /opt/salt
#-------------------------------------------------------------------------------
#BIN_DIR="$BUILD_DIR/opt/salt/bin"
#FILE="$BIN_DIR/start-*.sh"
#if ! compgen -G "$FILE" > /dev/null; then
#    _msg "Staging start scripts"
#    cp "$PKG_RESOURCES/scripts/start-*.sh" "$BIN_DIR/"
#    if compgen -G "$FILE" > /dev/null; then
#        _success
#    else
#        _failure
#    fi
#fi
#
#if ! [ -f "$BIN_DIR/salt-config.sh" ]; then
#    _msg "Staging Salt config script"
#    cp "$PKG_RESOURCES/scripts/salt-config.sh" "$BIN_DIR/"
#    if [ -f "$BIN_DIR/salt-config.sh" ]; then
#        _success
#    else
#        _failure
#    fi
#fi

SALT_DIR="$BUILD_DIR/opt/salt"
if ! [ -f "$SALT_DIR/salt-config.sh" ]; then
    _msg "Staging Salt config script"
    cp "$PKG_RESOURCES/scripts/salt-config.sh" "$SALT_DIR/"
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
    FILE="$BUILD_DIR/Library/LaunchDaemons/com.saltstack.salt.$i.com"
    if ! [ -f "$FILE" ]; then
        _msg "Copying $i service definition"
        cp "$PKG_RESOURCES/scripts/com.saltstack.salt.$i.plist" "$FILE"
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
    _failure
fi

# We need to do version first because Title contains version and we need to
# be able to check it
_msg "Setting package version"
SEDSTR="s/@VERSION@/$VERSION/g"
sed -E -i "" "$SEDSTR" "$DIST"
if grep -q "$VERSION" "$DIST"; then
    _success
else
    _failure
fi

_msg "Setting package title"
TITLE="Salt $VERSION (Python 3)"
SEDSTR="s/@TITLE@/$TITLE/g"
sed -E -i "" "$SEDSTR" "$DIST"
if grep -q "$TITLE" "$DIST"; then
    _success
else
    _failure
fi

_msg "Setting package description"
DESC="Salt $VERSION with Python 3"
SEDSTR="s/@DESC@/$DESC/g"
sed -E -i "" "$SEDSTR" "$DIST"
if grep -q "$DESC" "$DIST"; then
    _success
else
    _failure
fi

_msg "Setting package architecture"
SEDSTR="s/@CPU_ARCH@/$CPU_ARCH/g"
sed -i '' "$SEDSTR" "$DIST"
if grep -q "$CPU_ARCH" "$DIST"; then
    _success
else
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
