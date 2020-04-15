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
INSTALL_DIR=/opt/salt
PKG_CONFIG_PATH=$INSTALL_DIR/lib/pkgconfig
CFLAGS="-I$INSTALL_DIR/include"
LDFLAGS="-L$INSTALL_DIR/lib"
if [ "$PYVER" == "2" ]; then
    PYDIR=$INSTALL_DIR/lib/python2.7
    PYTHON=$INSTALL_DIR/bin/python
    PIP=$INSTALL_DIR/bin/pip
else
    PYDIR=$INSTALL_DIR/lib/python3.5
    PYTHON=$INSTALL_DIR/bin/python3
    PIP=$INSTALL_DIR/bin/pip3
fi

############################################################################
# Determine Which XCode is being used (XCode or XCode Command Line Tools)
############################################################################
# Prefer Xcode command line tools over any other gcc installed (e.g. MacPorts,
# Fink, Brew)
# Check for Xcode Command Line Tools first
if [ -d '/Library/Developer/CommandLineTools/usr/bin' ]; then
    PATH=/Library/Developer/CommandLineTools/usr/bin:$INSTALL_DIR/bin:$PATH
    MAKE=/Library/Developer/CommandLineTools/usr/bin/make
elif [ -d '/Applications/Xcode.app/Contents/Developer/usr/bin' ]; then
    PATH=/Applications/Xcode.app/Contents/Developer/usr/bin:$INSTALL_DIR/bin:$PATH
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
echo "################################################################################"
echo "Ensure Paths are present and clean"
echo "################################################################################"
echo -n -e "\033]0;Build_Env: Clean\007"

# Make sure $INSTALL_DIR is clean
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR
chown $USER:staff $INSTALL_DIR

# Make sure build staging is clean
rm -rf build
mkdir -p build
BUILDDIR=$SCRIPTDIR/build

############################################################################
# Download and install pkg-config
############################################################################
echo -n -e "\033]0;Build_Env: pkg-config: download\007"

PKGURL="http://pkgconfig.freedesktop.org/releases/pkg-config-0.29.2.tar.gz"
PKGDIR="pkg-config-0.29.2"

download $PKGURL

echo "################################################################################"
echo "Building pkg-config"
echo "################################################################################"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: pkg-config: configure\007"
env LDFLAGS="-framework CoreFoundation -framework Carbon" ./configure --prefix=$INSTALL_DIR --with-internal-glib
echo -n -e "\033]0;Build_Env: pkg-config: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: pkg-config: make check\007"
$MAKE check
echo -n -e "\033]0;Build_Env: pkg-config: make install\007"
$MAKE install

############################################################################
# Download and install libsodium
############################################################################
echo -n -e "\033]0;Build_Env: libsodium: download\007"

PKGURL="https://download.libsodium.org/libsodium/releases/libsodium-1.0.17.tar.gz"
PKGDIR="libsodium-1.0.17"

download $PKGURL

echo "################################################################################"
echo "Building libsodium"
echo "################################################################################"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: libsodium: configure\007"
./configure --prefix=$INSTALL_DIR
echo -n -e "\033]0;Build_Env: libsodium: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: libsodium: make check\007"
$MAKE check
echo -n -e "\033]0;Build_Env: libsodium: make install\007"
$MAKE install

############################################################################
# Download and install zeromq
############################################################################
echo -n -e "\033]0;Build_Env: zeromq: download\007"

PKGURL="https://github.com/zeromq/zeromq4-1/releases/download/v4.1.6/zeromq-4.1.6.tar.gz"
PKGDIR="zeromq-4.1.6"

download $PKGURL

echo "################################################################################"
echo "Building zeromq"
echo "################################################################################"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: zeromq: configure\007"
./configure --prefix=$INSTALL_DIR
echo -n -e "\033]0;Build_Env: zeromq: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: zeromq: make check\007"
$MAKE check
echo -n -e "\033]0;Build_Env: zeromq: make install\007"
$MAKE install

############################################################################
# Download and install OpenSSL
############################################################################
echo -n -e "\033]0;Build_Env: OpenSSL: download\007"

PKGURL="http://openssl.org/source/openssl-1.0.2q.tar.gz"
PKGDIR="openssl-1.0.2q"

download $PKGURL

echo "################################################################################"
echo "Building OpenSSL"
echo "################################################################################"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: OpenSSL: configure\007"
./Configure darwin64-x86_64-cc --prefix=$INSTALL_DIR --openssldir=$INSTALL_DIR/openssl
echo -n -e "\033]0;Build_Env: OpenSSL: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: OpenSSL: make test\007"
$MAKE test
echo -n -e "\033]0;Build_Env: OpenSSL: make install\007"
$MAKE install

############################################################################
# Download and install Python
############################################################################
echo -n -e "\033]0;Build_Env: Python: download\007"

if [ "$PYVER" == "2" ]; then
    PKGURL="https://www.python.org/ftp/python/2.7.15/Python-2.7.15.tar.xz"
    PKGDIR="Python-2.7.15"
else
    PKGURL="https://www.python.org/ftp/python/3.5.4/Python-3.5.4.tar.xz"
    PKGDIR="Python-3.5.4"
fi

download $PKGURL

echo "################################################################################"
echo "Building Python"
echo "################################################################################"
echo "Note there are some test failures"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: Python: configure\007"
./configure --prefix=$INSTALL_DIR --enable-shared --enable-toolbox-glue --with-ensurepip=install
echo -n -e "\033]0;Build_Env: Python: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: Python: make install\007"
$MAKE install

############################################################################
# upgrade pip
############################################################################
$PIP install --upgrade pip wheel

############################################################################
# Download and install salt python dependencies
############################################################################
echo -n -e "\033]0;Build_Env: PIP Dependencies\007"

cd $BUILDDIR

echo "################################################################################"
echo "Installing Salt Dependencies with pip (normal)"
echo "################################################################################"
$PIP install -r $SRCDIR/pkg/osx/req.txt -r $SRCDIR/pkg/osx/req_pyobjc.txt \
             --target=$PYDIR/site-packages \
             --ignore-installed \
             --no-cache-dir

echo "################################################################################"
echo "Installing Salt Dependencies with pip (build_ext)"
echo "################################################################################"
$PIP install -r $SRCDIR/pkg/osx/req_ext.txt \
             --global-option=build_ext \
             --global-option="-I$INSTALL_DIR/include" \
             --no-cache-dir

echo "--------------------------------------------------------------------------------"
echo "Create Symlink to certifi for openssl"
echo "--------------------------------------------------------------------------------"
ln -s $PYDIR/site-packages/certifi/cacert.pem $INSTALL_DIR/openssl/cert.pem

echo -n -e "\033]0;Build_Env: Finished\007"

cd $BUILDDIR

echo "################################################################################"
echo "Build Environment Script Completed"
echo "################################################################################"
