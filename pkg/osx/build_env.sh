#!/bin/bash

############################################################################
#
# Title: Build Environment Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script sets up a build environment for salt on macOS.
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script is not passed any parameters
#
#     Example:
#         The following will set up a build environment for salt on macOS
#
#         ./dev_env.sh
#
############################################################################

############################################################################
# Set to Exit on all Errors
############################################################################
trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit -1
}

############################################################################
# Parameters Required for the script to function properly
############################################################################
echo -n -e "\033]0;Build_Env: Variables\007"

# This is needed to allow the some test suites (zmq) to pass
ulimit -n 1200

SRCDIR=`git rev-parse --show-toplevel`
SCRIPTDIR=`pwd`
SHADIR=$SCRIPTDIR/shasums
PKG_CONFIG_PATH=/opt/salt/lib/pkgconfig
CFLAGS="-I/opt/salt/include"
LDFLAGS="-L/opt/salt/lib"

############################################################################
# Determine Which XCode is being used (XCode or XCode Command Line Tools)
############################################################################
# Prefer Xcode command line tools over any other gcc installed (e.g. MacPorts,
# Fink, Brew)
# Check for Xcode Command Line Tools first
if [ -d '/Library/Developer/CommandLineTools/usr/bin' ]; then
    PATH=/Library/Developer/CommandLineTools/usr/bin:/opt/salt/bin:$PATH
    MAKE=/Library/Developer/CommandLineTools/usr/bin/make
elif [ -d '/Applications/Xcode.app/Contents/Developer/usr/bin' ]; then
    PATH=/Applications/Xcode.app/Contents/Developer/usr/bin:/opt/salt/bin:$PATH
    MAKE=/Applications/Xcode.app/Contents/Developer/usr/bin/make
else
    echo "No installation of XCode found. This script requires XCode."
    exit -1
fi
export PATH

############################################################################
# Download Function
# - Downloads and verifies the MD5
############################################################################
download(){
    if [ -z "$1" ]; then
        echo "Must pass a URL to the download function"
    fi

    URL=$1
    PKGNAME=${URL##*/}

    cd $BUILDDIR

    echo "################################################################################"
    echo "Retrieving $PKGNAME"
    echo "################################################################################"
    curl -LO# $URL

    echo "################################################################################"
    echo "Comparing Sha512 Hash"
    echo "################################################################################"
    FILESHA=($(shasum -a 512 $PKGNAME))
    EXPECTEDSHA=($(cat $SHADIR/$PKGNAME.sha512))
    if [ "$FILESHA" != "$EXPECTEDSHA" ]; then
        echo "ERROR: Sha Check Failed for $PKGNAME"
        return 1
    fi

    echo "################################################################################"
    echo "Unpacking $PKGNAME"
    echo "################################################################################"
    tar -zxvf $PKGNAME

    return $?
}

############################################################################
# Ensure Paths are present and clean
############################################################################
echo -n -e "\033]0;Build_Env: Clean\007"

# Make sure /opt/salt is clean
sudo rm -rf /opt/salt
sudo mkdir -p /opt/salt
sudo chown $USER:staff /opt/salt

# Make sure build staging is clean
rm -rf build
mkdir -p build
BUILDDIR=$SCRIPTDIR/build

############################################################################
# Download and install pkg-config
############################################################################
echo -n -e "\033]0;Build_Env: pkg-config\007"

PKGURL="http://pkgconfig.freedesktop.org/releases/pkg-config-0.29.tar.gz"
PKGDIR="pkg-config-0.29"

download $PKGURL

echo "################################################################################"
echo "Building pkg-config"
echo "################################################################################"
cd $PKGDIR
env LDFLAGS="-framework CoreFoundation -framework Carbon" ./configure --prefix=/opt/salt --with-internal-glib
$MAKE
$MAKE check
sudo -H $MAKE install

############################################################################
# Download and install libsodium
############################################################################
echo -n -e "\033]0;Build_Env: libsodium\007"

PKGURL="https://download.libsodium.org/libsodium/releases/libsodium-1.0.12.tar.gz"
PKGDIR="libsodium-1.0.12"

download $PKGURL

echo "################################################################################"
echo "Building libsodium"
echo "################################################################################"
cd $PKGDIR
./configure --prefix=/opt/salt
$MAKE
$MAKE check
sudo -H $MAKE install

############################################################################
# Download and install zeromq
############################################################################
echo -n -e "\033]0;Build_Env: zeromq\007"

PKGURL="http://download.zeromq.org/zeromq-4.1.3.tar.gz"
PKGDIR="zeromq-4.1.3"

download $PKGURL

echo "################################################################################"
echo "Building zeromq"
echo "################################################################################"
cd $PKGDIR
./configure --prefix=/opt/salt
$MAKE
$MAKE check
sudo -H $MAKE install

############################################################################
# Download and install OpenSSL
############################################################################
echo -n -e "\033]0;Build_Env: OpenSSL\007"

PKGURL="http://openssl.org/source/openssl-1.0.2f.tar.gz"
PKGDIR="openssl-1.0.2f"

download $PKGURL

echo "################################################################################"
echo "Building OpenSSL 1.0.2f"
echo "################################################################################"
cd $PKGDIR
./Configure darwin64-x86_64-cc --prefix=/opt/salt --openssldir=/opt/salt/openssl
$MAKE
$MAKE test
sudo -H $MAKE install

############################################################################
# Download and install Python
############################################################################
echo -n -e "\033]0;Build_Env: Python\007"

PKGURL="https://www.python.org/ftp/python/2.7.12/Python-2.7.12.tar.xz"
PKGDIR="Python-2.7.12"

download $PKGURL

echo "################################################################################"
echo "Building Python 2.7.12"
echo "################################################################################"
echo "Note there are some test failures"
cd $PKGDIR
./configure --prefix=/opt/salt --enable-shared --enable-toolbox-glue --with-ensurepip=install
$MAKE
# $MAKE test
sudo -H $MAKE install

############################################################################
# upgrade pip
############################################################################
sudo -H /opt/salt/bin/pip install --upgrade pip

############################################################################
# Download and install salt python dependencies
############################################################################
echo -n -e "\033]0;Build_Env: PIP Dependencies\007"

cd $BUILDDIR

echo "################################################################################"
echo "Installing Salt Dependencies with pip (normal)"
echo "################################################################################"
sudo -H /opt/salt/bin/pip install \
                          -r $SRCDIR/pkg/osx/req.txt \
                          --no-cache-dir

echo "################################################################################"
echo "Installing Salt Dependencies with pip (build_ext)"
echo "################################################################################"
sudo -H /opt/salt/bin/pip install \
                          -r $SRCDIR/pkg/osx/req_ext.txt \
                          --global-option=build_ext \
                          --global-option="-I/opt/salt/include" \
                          --no-cache-dir

echo "--------------------------------------------------------------------------------"
echo "Create Symlink to certifi for openssl"
echo "--------------------------------------------------------------------------------"
sudo ln -s /opt/salt/lib/python2.7/site-packages/certifi/cacert.pem /opt/salt/openssl/cert.pem

echo -n -e "\033]0;Build_Env: Finished\007"

cd $BUILDDIR

echo "################################################################################"
echo "Build Environment Script Completed"
echo "################################################################################"
