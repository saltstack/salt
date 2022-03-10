#!/bin/bash
################################################################################
#
# Title: Build Salt Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script downloads and installs all dependencies and build
#              tools required to create a .pkg file for installation on macOS.
#              Salt and all dependencies will be installed to /opt/salt. A
#              .pkg file will then be created based on the contents of
#              /opt/salt. The pkg will be signed and notarized
#
#              This script must be run with sudo. In order for the environment
#              variables to be available in sudo you need to pass the `-E`
#              option. For example:
#
#              sudo -E ./build.sh 3003
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 3 parameters
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
# This script uses the following scripts:
#
#     build_env.sh
#         Builds python and other salt dependencies such as pkg-config,
#         libsodium, zeromq, and openssl.
#
#     sign_binaries.sh
#         Signs all the binaries with the Developer App certificate specified in
#         the DEV_APP_CERT environment variable. It signs all binaries in the
#         /opt/salt/bin and /opt/salt/lib directories. It also signs .dylib
#         files in the /opt/salt/lib directory.
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
echo "#########################################################################"
echo "Salt Package Build Script"
echo "#########################################################################"

################################################################################
# Make sure the script is launched with sudo
################################################################################
if [[ $(id -u) -ne 0 ]]; then
    echo ">>>>>> Re-launching as sudo <<<<<<"
    exec sudo /bin/bash -c "$(printf '%q ' "$BASH_SOURCE" "$@")"
fi

################################################################################
# Check passed parameters, set defaults
################################################################################
echo "**** Setting Variables"

if [ "$1" == "" ]; then
    VERSION=`git describe`
else
    VERSION=$1
fi

if [ "$2" == "" ]; then
    TEST_MODE="false"
else
    TEST_MODE=$2
fi

if [ "$3" == "" ]; then
    PKGDIR=/tmp/salt_pkg
else
    PKGDIR=$3
fi

################################################################################
# Additional Parameters Required for the script to function properly
################################################################################
SRCDIR=`git rev-parse --show-toplevel`
PKGRESOURCES=$SRCDIR/pkg/osx
PYTHON=/opt/salt/bin/python3
CPUARCH=`uname -m`

################################################################################
# Make sure this is the Salt Repository
################################################################################
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the root of the Git checkout."
    echo -en "\033]0;\a"
    exit -1
fi

################################################################################
# Create the Build Environment
################################################################################
echo "**** Building the environment"
$PKGRESOURCES/build_env.sh $TEST_MODE
if [[ "$?" != "0" ]]; then
    echo "Failed to build the environment."
    echo -en "\033]0;\a"
    exit -1
fi
################################################################################
# Install Salt
################################################################################
echo "**** Installing Salt into the environment"
echo -n -e "\033]0;Build: Install Salt\007"
rm -rf $SRCDIR/build
rm -rf $SRCDIR/dist
$PYTHON $SRCDIR/setup.py build -e "$PYTHON -E -s --upgrade"
$PYTHON $SRCDIR/setup.py install

################################################################################
# Sign Binaries built by Salt
################################################################################
echo "**** Signing binaries"
echo -n -e "\033]0;Build: Sign Binaries\007"
$PKGRESOURCES/sign_binaries.sh

################################################################################
# Build and Sign Package
################################################################################
echo "**** Building the package"
echo -n -e "\033]0;Build: Package Salt\007"
$PKGRESOURCES/package.sh $VERSION $PKGDIR

################################################################################
# Notarize Package
################################################################################
echo "**** Notarizing the package"
echo -n -e "\033]0;Build: Notarize Salt\007"
$PKGRESOURCES/notarize.sh salt-$VERSION-py3-$CPUARCH-signed.pkg
echo -en "\033]0;\a"
echo "#########################################################################"
echo "Salt Package Build Script Complete"
echo "#########################################################################"
