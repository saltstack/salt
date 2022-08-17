#!/bin/bash
################################################################################
#
# Title: Binary Signing Script for macOS
# Author: Shane Lee
# Date: December 2020
#
# Description: This signs all binaries built by the `build_env.sh` script as
#              well as those created by installing salt. It assumes a pyenv
#              environment in /opt/salt/.pyenv with salt installed
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
#         sudo ./sign_binaries
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
echo "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
echo "Signing Binaries"

################################################################################
# Make sure the script is launched with sudo
################################################################################
if [[ $(id -u) -ne 0 ]]; then
    echo ">>>>>> Re-launching as sudo <<<<<<"
    exec sudo -E /bin/bash -c "$(printf '%q ' "$BASH_SOURCE" "$@")"
fi

################################################################################
# Set to Exit on all Errors
################################################################################
trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit 1
}

################################################################################
# Environment Variables
################################################################################
echo "**** Setting Variables"
INSTALL_DIR=/opt/salt
PY_VERSION=3.9
PY_DOT_VERSION=3.9.12
CMD_OUTPUT=$(mktemp -t cmd.log)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

################################################################################
# Add rpath to the Python binaries before signing
################################################################################
echo "**** Setting rpath in binaries"
install_name_tool $INSTALL_DIR/bin/python${PY_VERSION} \
    -add_rpath $INSTALL_DIR/.pyenv/versions/$PY_DOT_VERSION/lib \
    -add_rpath $INSTALL_DIR/.pyenv/versions/$PY_DOT_VERSION/openssl/lib || echo "already present"

################################################################################
# Sign python binaries in `bin` and `lib`
################################################################################
echo "**** Signing binaries that have entitlements (/opt/salt/.pyenv)"
if ! find ${INSTALL_DIR}/.pyenv \
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
    echo "Failed to sign binaries"
    echo "Failed to sign run with entitlements"
    echo "output >>>>>>"
    cat "$CMD_OUTPUT" 1>&2
    echo "<<<<<< output"
    exit 1
fi

echo "**** Signing dynamic libraries (*dylib) (/opt/salt/.pyenv)"
if ! find ${INSTALL_DIR}/.pyenv \
    -type f \
    -name "*dylib" \
    -follow \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --force \
                   --sign "$DEV_APP_CERT" "{}" \; > "$CMD_OUTPUT" 2>&1; then
    echo "Failed to sign dynamic libraries"
    echo "output >>>>>>"
    cat "$CMD_OUTPUT" 1>&2
    echo "<<<<<< output"
    exit 1
fi

if ! echo "**** Signing shared libraries (*.so) (/opt/salt/.pyenv)"
find ${INSTALL_DIR}/.pyenv \
    -type f \
    -name "*.so" \
    -follow \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --force \
                   --sign "$DEV_APP_CERT" "{}" \;  > "$CMD_OUTPUT" 2>&1; then
    echo "Failed to sign shared libraries"
    echo "output >>>>>>"
    cat "$CMD_OUTPUT" 1>&2
    echo "<<<<<< output"
    exit 1
fi

echo "**** Signing Binaries Completed Successfully"
echo "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
