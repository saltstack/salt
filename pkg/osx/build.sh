#!/bin/bash
############################################################################
#
# Title: Build Salt Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script downloads and installs all dependencies and build
#              tools required to create a .pkg file for installation on macOS.
#              Salt and all dependencies will be installed to /opt/salt. A
#              .pkg file will then be created based on the contents of
#              /opt/salt
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 3 parameters
#         $1 : <version> : the version of salt to build
#                          (a git tag, not a branch)
#                          (defaults to git-repo state)
#         $2 : <pythin ver> : The version of Python to use in the
#                             build. Default is 2
#         $3 : <package dir> : the staging area for the package
#                              defaults to /tmp/salt_pkg
#
#     Example:
#         The following will build Salt v2015.8.3 with Python 2 and
#         stage all files in /tmp/custom_pkg:
#
#         ./build.sh v2015.8.3 2 /tmp/custom_pkg
#
############################################################################

############################################################################
# Make sure the script is launched with sudo
############################################################################
if [[ $(id -u) -ne 0 ]]
    then
        exec sudo /bin/bash -c "$(printf '%q ' "$BASH_SOURCE" "$@")"
fi

############################################################################
# Check passed parameters, set defaults
############################################################################
echo -n -e "\033]0;Build: Variables\007"

if [ "$1" == "" ]; then
    VERSION=`git describe`
else
    VERSION=$1
fi

if [ "$2" == "" ]; then
    PYVER=2
else
    PYVER=$2
fi

if [ "$3" == "" ]; then
    PKGDIR=/tmp/salt_pkg
else
    PKGDIR=$3
fi

############################################################################
# Additional Parameters Required for the script to function properly
############################################################################
SRCDIR=`git rev-parse --show-toplevel`
PKGRESOURCES=$SRCDIR/pkg/osx
if [ "$PYVER" == "2" ]; then
    PYTHON=/opt/salt/bin/python
else
    PYTHON=/opt/salt/bin/python3
fi
CPUARCH=`uname -m`

############################################################################
# Make sure this is the Salt Repository
############################################################################
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the root of the Git checkout."
    exit -1
fi

############################################################################
# Create the Build Environment
############################################################################
echo -n -e "\033]0;Build: Build Environment\007"
$PKGRESOURCES/build_env.sh $PYVER

############################################################################
# Install Salt
############################################################################
echo -n -e "\033]0;Build: Install Salt\007"
rm -rf $SRCDIR/build
rm -rf $SRCDIR/dist
$PYTHON $SRCDIR/setup.py build -e "$PYTHON -E -s"
$PYTHON $SRCDIR/setup.py install

############################################################################
# Build Package
############################################################################
echo -n -e "\033]0;Build: Package Salt\007"
$PKGRESOURCES/build_pkg.sh $VERSION $PYVER $PKGDIR

############################################################################
# Sign Package
############################################################################
$PKGRESOURCES/build_sig.sh salt-$VERSION-py$PYVER-$CPUARCH.pkg salt-$VERSION-py$PYVER-$CPUARCH-signed.pkg
