#!/bin/bash
################################################################################
#
# Title: Binary Signing Script for the macOS installer
# Author: Shane Lee
# Date: December 2020
#
# Description: This signs all binaries built by the `build_env.sh` script as
#              well as those created by installing salt. It assumes a python
#              environment in /opt/salt with salt installed
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script ignores any parameters passed to it
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
#               is missing the private key. This can be created by exporting the
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
echo "#########################################################################"
echo "Signing Binaries"

################################################################################
# Make sure the script is launched with sudo
################################################################################
if [[ $(id -u) -ne 0 ]]
    then
        exec sudo /bin/bash -c "$(printf '%q ' "$BASH_SOURCE" "$@")"
fi

################################################################################
# Set to Exit on all Errors
################################################################################
trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit -1
}

################################################################################
# Environment Variables
################################################################################
echo "**** Setting Variables"
INSTALL_DIR=/opt/salt

################################################################################
# Sign python binaries in `bin` and `lib`
################################################################################
echo "**** Signing binaries that have entitlements (/opt/salt/bin)"
find ${INSTALL_DIR}/bin \
    -type f \
    -perm -u=x \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --entitlements ./entitlements.plist \
                   --sign "$DEV_APP_CERT" "{}" \;

echo "**** Signing binaries (/opt/salt/lib)"
find ${INSTALL_DIR}/lib \
    -type f \
    -perm -u=x \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --sign "$DEV_APP_CERT" "{}" \;

echo "**** Signing dynamic libraries (*dylib) (/opt/salt/lib)"
find ${INSTALL_DIR}/lib \
    -type f \
    -name "*dylib" \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --sign "$DEV_APP_CERT" "{}" \;

echo "**** Signing shared libraries (*.so) (/opt/salt/lib)"
find ${INSTALL_DIR}/lib \
    -type f \
    -name "*.so" \
    -exec codesign --timestamp \
                   --options=runtime \
                   --verbose \
                   --sign "$DEV_APP_CERT" "{}" \;

echo "**** Signing Binaries Completed Successfully"
echo "#########################################################################"
