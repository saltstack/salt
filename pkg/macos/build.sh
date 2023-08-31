#!/bin/bash
################################################################################
#
# Title: Build Salt Package Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script downloads and installs all dependencies and build
#              tools required to create a .pkg file for installation on macOS.
#              Salt and all dependencies will be installed to a Relenv Python
#              environment in the ./build directory relevant to this script. A
#              .pkg file will then be created. The pkg will be signed and
#              notarized
#
#              If this script is run with sudo, you must pass the `-E` option
#              in order for the environment variables to be available. For
#              example:
#
#              sudo -E ./build.sh 3003
#
# Requirements:
#     - Xcode
#
#     NOTE: Previous versions of this script were able to run with just the
#           Xcode command line tools. However, now that we are notarizing these
#           packages, we require a full Xcode installation.
#
# Usage:
#     This script can be passed 3 positional arguments:
#         $1 : <version> : the version of salt to build
#                          (defaults to git-repo state)
#
#     Example:

#         # The following will build a Salt 3006.1-1 package:
#         ./build.sh 3006.1-1
#
#         # The following will build whatever version of salt is checked out:
#         ./build.sh
#
#         # The following will ensure environment variables are passed to the
#         # sudo environment:
#         sudo -E ./build.sh 3006.1-1
#
# This script calls out to the following scripts:
#
#     build_python.sh
#         Builds python using the relenv project:
#         https://github.com/saltstack/relative-environment-for-python
#
#     install_salt.sh
#         Installs Salt into the python environment
#
#     sign_binaries.sh
#         Signs all the binaries with the Developer App certificate specified in
#         the DEV_APP_CERT environment variable. It signs all binaries in the
#         ./build directory. It also signs all .dylib and .so files.
#
#     prep_salt.sh
#         Prepare the build environment for packaging. Stages config files and
#         service definitions. Removes files we don't want in the package.
#
#     package.sh
#         Builds a package file from the contents of ./build and signs it with
#         the Developer Installer certificate specified in the DEV_INSTALL_CERT
#         environment variable.
#
#     notarize.sh
#         Uploads the package to be notarized by Apple and staples the
#         notarization to the installer pkg. It uses the Apple Account name
#         specified in the APPLE_ACCT environment variable and the app-specific
#         password for that account specified in the APP_SPEC_PWD environment
#         variable.
#
# Environment Setup:
#     These scripts require certificates and environment variables be present on
#     the system. Details can be found in the individual scripts that use them.
#
#     Import Certificates:
#         Import the Salt Developer Application and Installer Signing
#         certificates using the following commands:
#
#         security import "developerID_application.p12" -k ~/Library/Keychains/login.keychain
#         security import "developerID_installer.p12" -k ~/Library/Keychains/login.keychain
#
#     Define Environment Variables:
#         Define the environment variables using the following commands (replace
#         with the actual values):
#
#         export DEV_APP_CERT="Developer ID Application: Salt Stack, Inc. (AB123ABCD1)"
#         export DEV_INSTALL_CERT="Developer ID Installer: Salt Stack, Inc. (AB123ABCD1)"
#         export APPLE_ACCT="username@domain.com"
#         export APP_SPEC_PWD="abcd-efgh-ijkl-mnop"
#
#         Don't forget to pass the `-E` option when running with Sudo so that
#         the environment variables are passed to the `package.sh`,
#         `notarize.sh`, and `sign_binaries.sh` scripts under the sudo
#         environment.
#
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
SRC_DIR="$(git rev-parse --show-toplevel)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CPU_ARCH=$(uname -m)

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to build a Salt package for macOS:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help] [-v|--version]"
     echo ""
     echo "  -h, --help      this message"
     echo "  -v, --version   version of Salt display in the package"
     echo ""
     echo "  Build a Salt package:"
     echo "      example: $0 3006.1-1"
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
            VERSION="$*"
            shift
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            exit 1
            ;;
        * )
            VERSION="$*"
            shift
            ;;
    esac
done

if [ -z "$VERSION" ]; then
    VERSION=$(git describe)
fi
VERSION=${VERSION#"v"}

#-------------------------------------------------------------------------------
# Quit on error
#-------------------------------------------------------------------------------
quit_on_error() {
    echo "$(basename "$0") caught error on line : $1 command was: $2"
    echo -en "\033]0;\a"
    exit 1
}
trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

#-------------------------------------------------------------------------------
# Make sure this is the Salt Repository
#-------------------------------------------------------------------------------
if [[ ! -e "$SRC_DIR/.git" ]] && [[ ! -e "$SRC_DIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a Salt git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo -en "\033]0;\a"
    exit 1
fi

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "#%.0s" {1..80}; printf "\n"
echo "Build Salt Package for macOS"
printf "v%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Build Python
#-------------------------------------------------------------------------------
"$SCRIPT_DIR/build_python.sh"

#-------------------------------------------------------------------------------
# Install Salt
#-------------------------------------------------------------------------------
"$SCRIPT_DIR/install_salt.sh"

#-------------------------------------------------------------------------------
# Sign Binaries built by Salt
#-------------------------------------------------------------------------------
"$SCRIPT_DIR/sign_binaries.sh"

#-------------------------------------------------------------------------------
# Prepare the Salt environment for packaging
#-------------------------------------------------------------------------------
"$SCRIPT_DIR/prep_salt.sh"

#-------------------------------------------------------------------------------
# Build and Sign Package
#-------------------------------------------------------------------------------
if [ "$(id -un)" != "root" ]; then
    sudo "$SCRIPT_DIR/package.sh" "$VERSION"
else
    "$SCRIPT_DIR/package.sh" "$VERSION"
fi

#-------------------------------------------------------------------------------
# Notarize Package
#-------------------------------------------------------------------------------
"$SCRIPT_DIR/notarize.sh" "salt-$VERSION-py3-$CPU_ARCH-signed.pkg"

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
printf "^%.0s" {1..80}; printf "\n"
echo "Build Salt Package for macOS Complete"
printf "#%.0s" {1..80}; printf "\n"
