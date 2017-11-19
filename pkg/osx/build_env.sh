#!/bin/bash

############################################################################
#
# Title: Build Environment Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script sets up a build environment for Salt on macOS.
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 1 parameter
#       $1 : <python version> : the version of Python to use for the
#                               build environment. Default is 2
#
#     Example:
#         The following will set up a Python 3 build environment for Salt
#         on macOS
#
#         ./dev_env.sh 3
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
# Check passed parameters, set defaults
############################################################################
if [ "$1" == "" ]; then
    PYVER=2
else
    PYVER=$1
fi

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
if [ "$PYVER" == "2" ]; then
    PYDIR=/opt/salt/lib/python2.7
    PYTHON=/opt/salt/bin/python
    PIP=/opt/salt/bin/pip
else
    PYDIR=/opt/salt/lib/python3.5
    PYTHON=/opt/salt/bin/python3
    PIP=/opt/salt/bin/pip3
fi

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

PKGURL="http://pkgconfig.freedesktop.org/releases/pkg-config-0.29.2.tar.gz"
PKGDIR="pkg-config-0.29.2"

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

PKGURL="https://download.libsodium.org/libsodium/releases/libsodium-1.0.13.tar.gz"
PKGDIR="libsodium-1.0.13"

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

PKGURL="http://download.zeromq.org/zeromq-4.1.4.tar.gz"
PKGDIR="zeromq-4.1.4"

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

PKGURL="http://openssl.org/source/openssl-1.0.2l.tar.gz"
PKGDIR="openssl-1.0.2l"

download $PKGURL

echo "################################################################################"
echo "Building OpenSSL"
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

if [ "$PYVER" == "2" ]; then
    PKGURL="https://www.python.org/ftp/python/2.7.13/Python-2.7.13.tar.xz"
    PKGDIR="Python-2.7.13"
else
    PKGURL="https://www.python.org/ftp/python/3.5.3/Python-3.5.3.tar.xz"
    PKGDIR="Python-3.5.3"
fi

download $PKGURL

echo "################################################################################"
echo "Building Python"
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
sudo -H $PIP install --upgrade pip

############################################################################
# Download and install salt python dependencies
############################################################################
echo -n -e "\033]0;Build_Env: PIP Dependencies\007"

cd $BUILDDIR

echo "################################################################################"
echo "Installing Salt Dependencies with pip (normal)"
echo "################################################################################"
sudo -H $PIP install \
     -r $SRCDIR/pkg/osx/req.txt \
     --no-cache-dir

echo "################################################################################"
echo "Installing Salt Dependencies with pip (build_ext)"
echo "################################################################################"
sudo -H $PIP install \
     -r $SRCDIR/pkg/osx/req_ext.txt \
     --global-option=build_ext \
     --global-option="-I/opt/salt/include" \
     --no-cache-dir

echo "--------------------------------------------------------------------------------"
echo "Create Symlink to certifi for openssl"
echo "--------------------------------------------------------------------------------"
sudo ln -s $PYDIR/site-packages/certifi/cacert.pem /opt/salt/openssl/cert.pem

echo -n -e "\033]0;Build_Env: Finished\007"

cd $BUILDDIR

echo "################################################################################"
echo "Build Environment Script Completed"
echo "################################################################################"
