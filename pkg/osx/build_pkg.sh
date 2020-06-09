#!/bin/bash
############################################################################
#
# Title: Build Package Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This creates an macOS package for Salt from the contents of
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
#         ./build.sh 2017.7.0 3
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
# Set to Exit on all Errors
############################################################################
trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit -1
}

############################################################################
# Check passed parameters, set defaults
############################################################################
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

############################################################################
# Additional Parameters Required for the script to function properly
############################################################################
echo -n -e "\033]0;Build_Pkg: Variables\007"

SRCDIR=`git rev-parse --show-toplevel`
PKGRESOURCES=$SRCDIR/pkg/osx

############################################################################
# Make sure this is the Salt Repository
############################################################################
if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The macOS build process needs some files from a Git checkout of Salt."
    echo "Run this script from the 'pkg/osx' directory of the Git checkout."
    exit -1
fi

############################################################################
# Ensure Paths are present and clean
############################################################################
echo -n -e "\033]0;Build_Pkg: Clean Staging Area\007"

# Clean folder in the staging area
rm -rdf $PKGDIR
mkdir -p $PKGDIR

############################################################################
# Copy Start Scripts from Salt Repo to /opt/salt
############################################################################
echo -n -e "\033]0;Build_Pkg: Copy Start Scripts\007"

cp $PKGRESOURCES/scripts/start-*.sh /opt/salt/bin/
cp $PKGRESOURCES/scripts/salt-config.sh /opt/salt/bin

############################################################################
# Copy Service Definitions from Salt Repo to the Package Directory
############################################################################
echo -n -e "\033]0;Build_Pkg: Copy Service Definitions\007"

mkdir -p $PKGDIR/opt
cp -r /opt/salt $PKGDIR/opt
mkdir -p $PKGDIR/Library/LaunchDaemons $PKGDIR/etc

cp $PKGRESOURCES/scripts/com.saltstack.salt.minion.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.master.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.syndic.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.api.plist $PKGDIR/Library/LaunchDaemons

############################################################################
# Remove unnecessary files from the package
############################################################################
echo -n -e "\033]0;Build_Pkg: Trim unneeded files\007"

rm -rdf $PKGDIR/opt/salt/bin/pkg-config
rm -rdf $PKGDIR/opt/salt/lib/pkgconfig
rm -rdf $PKGDIR/opt/salt/lib/engines
rm -rdf $PKGDIR/opt/salt/share/aclocal
rm -rdf $PKGDIR/opt/salt/share/doc
rm -rdf $PKGDIR/opt/salt/share/man/man1/pkg-config.1
rm -rdf $PKGDIR/opt/salt/lib/python3.7/test


echo -n -e "\033]0;Build_Pkg: Remove compiled python files\007"
find $PKGDIR/opt/salt -name '*.pyc' -type f -delete

############################################################################
# Copy Config Files from Salt Repo to the Package Directory
############################################################################
echo -n -e "\033]0;Build_Pkg: Copy Config Files\007"

mkdir -p $PKGDIR/etc/salt
cp $SRCDIR/conf/minion $PKGDIR/etc/salt/minion.dist
cp $SRCDIR/conf/master $PKGDIR/etc/salt/master.dist

############################################################################
# Add Version and CPU Arch to distribution.xml
############################################################################
echo -n -e "\033]0;Build_Pkg: Add Version to .xml\007"

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

############################################################################
# Build the Package
############################################################################
echo -n -e "\033]0;Build_Pkg: Build Package\007"

pkgbuild --root=$PKGDIR \
         --scripts=pkg-scripts \
         --identifier=com.saltstack.salt \
         --version=$VERSION \
         --ownership=recommended salt-src-$VERSION-py3-$CPUARCH.pkg

productbuild --resources=pkg-resources \
             --distribution=distribution.xml  \
             --package-path=salt-src-$VERSION-py3-$CPUARCH.pkg \
             --version=$VERSION salt-$VERSION-py3-$CPUARCH.pkg

