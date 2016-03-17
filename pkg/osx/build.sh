#!/bin/bash
############################################################################
#
# Title: Build Salt Script for OSX
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script downloads and installs all dependencies and build
#              tools required to create a .pkg file for installation on OSX.
#              Salt and all dependencies will be installed to /opt/salt. A
#              .pkg file will then be created based on the contents of
#              /opt/salt
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 3 parameters
#         $1 : <package dir> : the staging area for the package
#                              defaults to /tmp/salt-pkg
#         $2 : <version> : the version of salt to build
#                          (a git tag, not a branch)
#                          (defaults to git-repo state)
#
#     Example:
#         The following will build Salt v2015.8.3 and stage all files
#         in /tmp/pkg:
#
#         ./build.sh /tmp/pkg v2015.8.3
#
############################################################################

echo -n -e "\033]0;Build: Variables\007"

############################################################################
# Check passed parameters, set defaults
############################################################################
if [ "$1" == "" ]; then
    PKGDIR=/tmp/pkg
else
    PKGDIR=$1
fi

if [ "$2" == "" ]; then
    VERSION=`git describe`
else
    VERSION=$2
fi


############################################################################
# Additional Parameters Required for the script to function properly
############################################################################

SRCDIR=`git rev-parse --show-toplevel`
PKGRESOURCES=$SRCDIR/pkg/osx


############################################################################
# Make sure this is the Salt Repository
############################################################################
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The OS X build process needs some files from a Git checkout of Salt."
    echo "Run this script from the root of the Git checkout."
    exit -1
fi


############################################################################
# Create the Build Environment
############################################################################
echo -n -e "\033]0;Build: Build Environment\007"
$PKGRESOURCES/build_env.sh


############################################################################
# Install Salt
############################################################################
echo -n -e "\033]0;Build: Install Salt\007"
sudo /opt/salt/bin/python $SRCDIR/setup.py install


############################################################################
# Build Package
############################################################################
echo -n -e "\033]0;Build: Package Salt\007"
$PKGRESOURCES/build_pkg.sh $PKGDIR $VERSION
