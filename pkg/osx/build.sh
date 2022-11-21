#!/bin/bash
################################################################################
#
# Title: Build Salt Package Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script downloads and installs all dependencies and build
#              tools required to create a .pkg file for installation on macOS.
#              Salt and all dependencies will be installed to a pyenv
#              environment in /opt/salt. A .pkg file will then be created based
#              on the contents of /opt/salt. The pkg will be signed and
#              notarized
#
#              This script must be run with sudo. In order for the environment
#              variables to be available in sudo you need to pass the `-E`
#              option. For example:
#
#              sudo -E ./build.sh 3003
#
# Requirements:
#     - Xcode
#
# Usage:
#     This script can be passed 3 positional arguments:
#         $1 : <version> : the version of salt to build
#                          (a git tag, not a branch)
#                          (defaults to git-repo state)
#         $2 : <test mode> : if this script should be run in test mode, this
#                            disables the longer optimized compile time of python.
#                            Please DO NOT set to "true" when building a
#                            release version.
#                            (defaults to false)
#         $3 : <package dir> : the staging area for the package
#                              defaults to /tmp/salt_pkg
#
#     Example:
#         The following will build Salt v3001 with an optimized python and
#         stage all files in /tmp/custom_pkg:
#
#         sudo -E ./build.sh 3001 false /tmp/custom_pkg
#
# This script calls out to the following scripts:
#
#     build_env.sh
#         Builds python using pyenv, libsodium, and zeromq. OpenSSL and Readline
#         are compiled by pyenv.
#
#     sign_binaries.sh
#         Signs all the binaries with the Developer App certificate specified in
#         the DEV_APP_CERT environment variable. It signs all binaries in the
#         /opt/salt/.pyenv directory. It also signs all .dylib and .so files in
#         the /opt/salt/.pyenv directory.
#
#     package.sh
#         Builds a package file from the contents of /opt/salt and signs it with
#         the Developer Installer certificate specified in the DEV_INSTALL_CERT
#         environment variable.
#
#     notarize.sh
#         Sends the package to be notarized by apple and staples the
#         notarization to the installer pkg. It uses the Apple Account name
#         specified in the APPLE_ACCT environment variable and the app-specific
#         password for that account specified in the APP_SPEC_PWD environment
#         variable.
#
# Environment Setup:
#     This script requires certificates and environment variables be present on
#     the system. They are used by the above scripts. Details can be found in
#     the individual scripts that use them.
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
#         Don't forget to run sudo with the `-E` option so that the environment
#         variables are passed to the `package.sh`, `notarize.sh`, and
#         `sign_binaries.sh` scripts under the sudo environment.
#
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
SRCDIR=`git rev-parse --show-toplevel`
SCRIPT_DIR=$SRCDIR/pkg/osx
CPUARCH=`uname -m`

if [ "$1" == "" ]; then
    VERSION=`git describe`
else
    VERSION=$1
fi

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
 _usage() {
     echo ""
     echo "Script to build a Salt package for MacOS:"
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
# Make sure this is the Salt Repository
#-------------------------------------------------------------------------------
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a Salt git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo -en "\033]0;\a"
    exit 1
fi

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "#%.0s" {1..80}; printf "\n"
echo "Build Salt Package for MacOS"
printf "v%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Build Python
#-------------------------------------------------------------------------------
$SCRIPT_DIR/build_python.sh

#-------------------------------------------------------------------------------
# Install Salt
#-------------------------------------------------------------------------------
$SCRIPT_DIR/install_salt.sh

#-------------------------------------------------------------------------------
# Sign Binaries built by Salt
#-------------------------------------------------------------------------------
$SCRIPT_DIR/sign_binaries.sh

#-------------------------------------------------------------------------------
# Build and Sign Package
#-------------------------------------------------------------------------------
$SCRIPT_DIR/package.sh $VERSION $PKGDIR

#-------------------------------------------------------------------------------
# Notarize Package
#-------------------------------------------------------------------------------
$SCRIPT_DIR/notarize.sh salt-$VERSION-py3-$CPUARCH-signed.pkg

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
printf "^%.0s" {1..80}; printf "\n"
echo "Build Salt Package for MacOS Coplete"
printf "#%.0s" {1..80}; printf "\n"
