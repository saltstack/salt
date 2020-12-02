#!/bin/bash
################################################################################
#
# Title: Binary Signing Script for macOS installer
# Authors: CR Oldham, Shane Lee
# Date: December 2020
#
# Description: This signs all binaries built by the `build_env.sh` script
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Environment Setup:
#
#     Import Certificates:
#         Import the Salt Developer Application Signing certificate using the
#         following command:
#
#         security import "developerID_application.cer" -k ~/Library/Keychains/login.keychain
#
#     Define Environment Variables:
#         Create an environment variable with the name of the certificate to use
#         from the keychain for binary signing. Use the following command (The
#         actual value must match what is provided in the certificate):
#
#         export DEV_APP_CERT="Developer ID Application: Salt Stack, Inc. (AB123ABCD1)"
#
################################################################################

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
# Sign python binaries in `bin` and `lib`
################################################################################
INSTALL_DIR=/opt/salt
find ${INSTALL_DIR}/bin \
    -type f \
    -perm -u=x \
    -exec codesign --timestamp --verbose --sign "$DEV_APP_CERT" "{}" \;
find ${INSTALL_DIR}/lib \
    -type f \
    -perm -u=x \
    -exec codesign --timestamp --verbose --sign "$DEV_APP_CERT" "{}" \;
find ${INSTALL_DIR}/lib \
    -type f \
    -name "*dylib" \
    -exec codesign --timestamp --verbose --sign "$DEV_APP_CERT" "{}" \;
