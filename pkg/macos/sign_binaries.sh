#!/bin/bash
################################################################################
#
# Title: Binary Signing Script for macOS
# Author: Shane Lee
# Date: December 2020
#
# Description: This signs all binaries built by the `build_python.sh` and the
#              `installing_salt.sh` scripts.
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#       or
#     - Xcode
#
# Usage:
#     This script does not require any parameters.
#
#     Example:
#
#         ./sign_binaries
#
# Environment Setup:
#
#     Import Certificates:
#         Import the Salt Developer Application Signing certificate using the
#         following command:
#
#         security import "developerID_application.p12" -k ~/Library/Keychains/login.keychain
#
#         NOTE: The .p12 certificate is required as the .cer certificate is
#               missing the private key. This can be created by exporting the
#               certificate from the machine it was created on
#
#     Define Environment Variables:
#         Create an environment variable with the name of the certificate to use
#         from the keychain for binary signing. Use the following command (The
#         actual value must match what is provided in the certificate):
#
#         export DEV_APP_CERT="Developer ID Application: Salt Stack, Inc. (AB123ABCD1)"
#
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
CMD_OUTPUT=$(mktemp -t cmd.log)

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to sign binaries in preparation for packaging:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help]"
     echo ""
     echo "  -h, --help      this message"
     echo ""
     echo "  To sign binaries:"
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
    printf '\e[32m%s\e[0m\n' "Success"
}

# _failure
#
#   Prints a red Failure and exits
_failure() {
    printf '\e[31m%s\e[0m\n' "Failure"
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
echo "Sign Binaries"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Sign python binaries in `bin` and `lib`
#-------------------------------------------------------------------------------
_msg "Signing binaries with entitlements"
if find "$BUILD_DIR" \
    -type f \
    -perm -u=x \
    -follow \
    ! -name "*.so" \
    ! -name "*.dylib" \
    ! -name "*.py" \
    ! -name "*.sh" \
    ! -name "*.bat" \
    ! -name "*.pl" \
    ! -name "*.crt" \
    ! -name "*.key" \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --force \
                   --entitlements "$SCRIPT_DIR/entitlements.plist" \
                   --sign "$DEV_APP_CERT" "{}" \; > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi

_msg "Signing dynamic libraries (*dylib)"
if find "$BUILD_DIR" \
    -type f \
    -name "*dylib" \
    -follow \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --force \
                   --sign "$DEV_APP_CERT" "{}" \; > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi

_msg "Signing shared libraries (*.so)"
if find "$BUILD_DIR" \
    -type f \
    -name "*.so" \
    -follow \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --force \
                   --sign "$DEV_APP_CERT" "{}" \;  > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Script Complete
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Sign Binaries Complete"
printf "=%.0s" {1..80}; printf "\n"
