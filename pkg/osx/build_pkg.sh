#!/bin/bash
############################################################################
#
# Title: Build Package Script for OSX
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This creates an OSX package for Salt from the contents of
#              /opt/salt
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 2 parameters
#         $1 : <package dir> : the staging area for the package defaults to
#              /tmp/salt-pkg
#         $2 : <version> : the version name to give the package (overrides
#              version of the git repo) (Defaults to the git repo version)
#
#     Example:
#         The following will build Salt and stage all files in /tmp/pkg:
#
#         ./build.sh /tmp/pkg
#
############################################################################

trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit -1
}

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

echo -n -e "\033]0;Build_Pkg: Variables\007"

SRCDIR=`git rev-parse --show-toplevel`

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
# Ensure Paths are present and clean
############################################################################

echo -n -e "\033]0;Build_Pkg: Clean Staging Area\007"

# Clean folder in the staging area
rm -rdf $PKGDIR
mkdir -p $PKGDIR

PKGRESOURCES=$SRCDIR/pkg/osx

############################################################################
# Create Symbolic Links to Salt Binaries
############################################################################

echo -n -e "\033]0;Build_Pkg: Create Symbolic Links\007"

cd /opt/salt
for f in /opt/salt/bin/salt-*; do
    if [ ! -f $f ]; then
        ln -s $f /opt/salt
    fi
done

if [ ! -f /opt/salt/bin/spm ];  then
    ln -s /opt/salt/bin/spm /opt/salt
fi
if [ ! -f /opt/salt/bin/raetflo ];  then
    ln -s /opt/salt/bin/raetflo /opt/salt
fi
if [ ! -f /opt/salt/bin/ioflo ];  then
    ln -s /opt/salt/bin/ioflo /opt/salt
fi
if [ ! -f /opt/salt/bin/ioflo2 ];  then
    ln -s /opt/salt/bin/ioflo2 /opt/salt
fi

############################################################################
# Copy Start Scripts from Salt Repo to /opt/salt
############################################################################

echo -n -e "\033]0;Build_Pkg: Copy Start Scripts\007"

sudo cp $PKGRESOURCES/scripts/start-*.sh /opt/salt/bin/

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
# Remove pkg-config files from the distro 
############################################################################

echo -n -e "\033]0;Build_Pkg: Remove pkg-config files\007"

sudo rm -rdf $PKGDIR/opt/salt/bin/pkg-config
sudo rm -rdf $PKGDIR/opt/salt/lib/pkgconfig
sudo rm -rdf $PKGDIR/opt/salt/lib/engines
sudo rm -rdf $PKGDIR/opt/salt/share/aclocal
sudo rm -rdf $PKGDIR/opt/salt/share/doc
sudo rm -rdf $PKGDIR/opt/salt/share/man/man1/pkg-config.1

############################################################################
# Copy Additional Resources from Salt Repo to the Package Directory
############################################################################

echo -n -e "\033]0;Build_Pkg: Copy Additional Resources\007"

mkdir -p $PKGDIR/resources
cp $PKGRESOURCES/saltstack.png $PKGDIR/resources
cp $PKGRESOURCES/*.rtf $PKGDIR/resources

# I can't get this to work for some reason
mkdir -p $PKGDIR/scripts
cp $PKGRESOURCES/scripts/postinstall $PKGDIR/scripts
cp $PKGRESOURCES/scripts/preinstall $PKGDIR/scripts

############################################################################
# Copy Config Files from Salt Repo to the Package Directory
############################################################################

echo -n -e "\033]0;Build_Pkg: Copy Config Files\007"

mkdir -p $PKGDIR/etc/salt
cp $SRCDIR/conf/minion $PKGDIR/etc/salt/minion.dist
cp $SRCDIR/conf/master $PKGDIR/etc/salt/master.dist

############################################################################
# Add Version to distribution.xml
############################################################################

echo -n -e "\033]0;Build_Pkg: Add Version to .xml\007"

cd $PKGRESOURCES
cp distribution.xml.dist distribution.xml
SEDSTR="s/@VERSION@/$VERSION/"
echo $SEDSTR
sed -i '' $SEDSTR distribution.xml

############################################################################
# Build the Package
############################################################################

echo -n -e "\033]0;Build_Pkg: Build Package\007"

pkgbuild --root $PKGDIR \
         --scripts $PKGDIR/scripts \
         --identifier=com.saltstack.salt \
         --version=$VERSION \
         --ownership=recommended salt-src-$VERSION.pkg

productbuild --resources=$PKGDIR/resources \
             --distribution=distribution.xml  \
             --package-path=salt-src-$VERSION.pkg \
             --version=$VERSION salt-$VERSION.pkg

