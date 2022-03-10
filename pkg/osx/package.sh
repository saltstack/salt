#!/bin/bash
################################################################################
#
# Title: Build Package Script for the macOS installer
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This creates a signed macOS package for Salt from the contents of
#              /opt/salt
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 2 parameters
#         $1 : <version> : the version name to give the package (overrides
#              version of the git repo) (Defaults to the git repo version)
#         $2 : <package dir> : the staging area for the package defaults to
#              /tmp/salt_pkg
#
#     Example:
#         The following will build Salt version 2017.7.0 with Python 3 and
#         stage all files in /tmp/salt_pkg:
#
#         ./package.sh 2017.7.0 /tmp/salt_pkg
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
#               is missing the private key. This can be created by exporting the
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
echo "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
echo "Building Salt Package"

################################################################################
# Make sure the script is launched with sudo
################################################################################
if [[ $(id -u) -ne 0 ]]; then
    echo ">>>>>> Re-launching as sudo <<<<<<"
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
# Check passed parameters, set defaults
################################################################################
# Get/Set Version
if [ "$1" == "" ]; then
    VERSION=`git describe`
else
    VERSION=$1
fi

# Get/Set temp directory
if [ "$2" == "" ]; then
    PKGDIR=/tmp/salt_pkg
else
    PKGDIR=$2
fi

CPUARCH=`uname -m`

################################################################################
# Additional Parameters Required for the script to function properly
################################################################################
echo "**** Setting Variables"

SRCDIR=`git rev-parse --show-toplevel`
PKGRESOURCES=$SRCDIR/pkg/osx

################################################################################
# Make sure this is the Salt Repository
################################################################################
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the 'pkg/osx' directory of the Git checkout."
    exit -1
fi

################################################################################
# Ensure Paths are present and clean
################################################################################
echo "**** Cleaning Staging Area"

# Clean folder in the staging area
rm -rdf $PKGDIR
mkdir -p $PKGDIR

################################################################################
# Copy Start Scripts from Salt Repo to /opt/salt
################################################################################
echo "**** Copying Start Scripts"

cp $PKGRESOURCES/scripts/start-*.sh /opt/salt/bin/
cp $PKGRESOURCES/scripts/salt-config.sh /opt/salt/bin

################################################################################
# Copy Service Definitions from Salt Repo to the Package Directory
################################################################################

echo "**** Copying Build Files"
mkdir -p $PKGDIR/opt/salt
cp -r /opt/salt/.pyenv $PKGDIR/opt/salt/.pyenv

echo "**** Copying Service Definitions"
mkdir -p $PKGDIR/Library/LaunchDaemons $PKGDIR/etc

cp $PKGRESOURCES/scripts/com.saltstack.salt.minion.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.master.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.syndic.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.api.plist $PKGDIR/Library/LaunchDaemons

################################################################################
# Remove unnecessary files from the package
################################################################################
echo "**** Trimming Unneeded Files"

rm -rdf $PKGDIR/opt/salt/.pyenv/lib/pkgconfig
rm -rdf $PKGDIR/opt/salt/.pyenv/versions/3.7.12/lib/pkgconfig
rm -rdf $PKGDIR/opt/salt/.pyenv/versions/3.7.12/lib/engines*
rm -rdf $PKGDIR/opt/salt/.pyenv/versions/3.7.12/lib/python3.7/test
rm -rdf $PKGDIR/opt/salt/.pyenv/versions/3.7.12/lib/python3.7/site-packages/Cryptodome/SelfTest
rm -rdf $PKGDIR/opt/salt/.pyenv/versions/3.7.12/lib/python3.7/site-packages/libcloud/test

echo "**** Removing Unneded documentation"
find $PKGDIR/opt/salt -name 'share' -type d -prune -exec rm -rf {} \;

echo "**** Removing Compiled Python Files (.pyc/__pycache__)"
find $PKGDIR/opt/salt -name '*.pyc' -type f -delete
find $PKGDIR/opt/salt -name '__pycache__' -type d -prune -exec rm -rf {} \;

################################################################################
# Copy Config Files from Salt Repo to the Package Directory
################################################################################
echo "**** Copying Config Files"

mkdir -p $PKGDIR/etc/salt
cp $SRCDIR/conf/minion $PKGDIR/etc/salt/minion.dist
cp $SRCDIR/conf/master $PKGDIR/etc/salt/master.dist

################################################################################
# Add Title, Description, Version and CPU Arch to distribution.xml
################################################################################
echo "**** Modifying distribution.xml"

TITLE="Salt $VERSION (Python 3)"
DESC="Salt $VERSION with Python 3"

cd $PKGRESOURCES
cp distribution.xml.dist distribution.xml

SEDSTR="s/@TITLE@/$TITLE/g"
sed -E -i '' "$SEDSTR" distribution.xml

SEDSTR="s/@DESC@/$DESC/g"
sed -E -i '' "$SEDSTR" distribution.xml

SEDSTR="s/@VERSION@/$VERSION/g"
sed -E -i '' "$SEDSTR" distribution.xml

SEDSTR="s/@CPUARCH@/$CPUARCH/g"
sed -i '' "$SEDSTR" distribution.xml

################################################################################
# Build the Package
################################################################################
echo "**** Building the Source Package"

# Build the src package
pkgbuild --root=$PKGDIR \
         --scripts=pkg-scripts \
         --identifier=com.saltstack.salt \
         --version=$VERSION \
         --ownership=recommended \
         salt-src-$VERSION-py3-$CPUARCH.pkg > /dev/null

echo "**** Building and Signing the Product Package with Timestamp"
productbuild --resources=pkg-resources \
             --distribution=distribution.xml  \
             --package-path=salt-src-$VERSION-py3-$CPUARCH.pkg \
             --version=$VERSION \
             --sign "$DEV_INSTALL_CERT" \
             --timestamp \
             salt-$VERSION-py3-$CPUARCH-signed.pkg > /dev/null

echo "Building Salt Package Completed Successfully"
echo "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
