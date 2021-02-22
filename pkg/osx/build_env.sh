#!/bin/bash
################################################################################
#
# Title: Build Environment Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script sets up a build environment for Salt on macOS.
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 1 parameter
#       $1 : <test mode> :   if this script should be run in test mode, this
#                            disables the longer optimized compile time of python.
#                            Please DO NOT set to "true" when building a
#                            release version.
#                            (defaults to false)
#
#     Example:
#         The following will set up an optimized Python build environment for Salt
#         on macOS
#
#         ./dev_env.sh
#
################################################################################

################################################################################
# Make sure the script is launched with sudo
################################################################################
if [[ $(id -u) -ne 0 ]]
    then
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
# Parameters Required for the script to function properly
################################################################################
echo -n -e "\033]0;Build_Env: Variables\007"

MACOSX_DEPLOYMENT_TARGET=10.13
export MACOSX_DEPLOYMENT_TARGET

# This is needed to allow the some test suites (zmq) to pass
# taken from https://github.com/zeromq/libzmq/issues/1878
SET_ULIMIT=200000
sysctl -w kern.maxfiles=$SET_ULIMIT
sysctl -w kern.maxfilesperproc=$SET_ULIMIT
launchctl limit maxfiles $SET_ULIMIT $SET_ULIMIT
ulimit -n $SET_ULIMIT

PY_VERSION=3.7
SRCDIR=`git rev-parse --show-toplevel`
SCRIPTDIR=`pwd`
SHADIR=$SCRIPTDIR/shasums
INSTALL_DIR=/opt/salt
PKG_CONFIG=$INSTALL_DIR/bin/pkg-config
PKG_CONFIG_PATH=$INSTALL_DIR/lib/pkgconfig
PYDIR=$INSTALL_DIR/lib/python$PY_VERSION
PYTHON=$INSTALL_DIR/bin/python3
PIP=$INSTALL_DIR/bin/pip3

# needed for python to find pkg-config and have pkg-config properly link
# the python install to the compiled openssl below.
export PKG_CONFIG
export PKG_CONFIG_PATH

################################################################################
# Determine Which XCode is being used (XCode or XCode Command Line Tools)
################################################################################
# Prefer Xcode command line tools over any other gcc installed (e.g. MacPorts,
# Fink, Brew)
# Check for Xcode Command Line Tools first
if [ -d '/Library/Developer/CommandLineTools/usr/bin' ]; then
    MAKE=/Library/Developer/CommandLineTools/usr/bin/make
elif [ -d '/Applications/Xcode.app/Contents/Developer/usr/bin' ]; then
    MAKE=/Applications/Xcode.app/Contents/Developer/usr/bin/make
else
    echo "No installation of XCode found. This script requires XCode."
    echo "Try running: xcode-select --install"
    exit -1
fi

################################################################################
# Download Function
# - Downloads and verifies the MD5
################################################################################
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

################################################################################
# Ensure Paths are present and clean
################################################################################
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

################################################################################
# Download and install pkg-config
################################################################################
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

################################################################################
# Download and install libsodium
################################################################################
echo -n -e "\033]0;Build_Env: libsodium: download\007"

PKGURL="https://download.libsodium.org/libsodium/releases/libsodium-1.0.18.tar.gz"
PKGDIR="libsodium-1.0.18"

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

################################################################################
# Download and install zeromq
################################################################################
echo -n -e "\033]0;Build_Env: zeromq: download\007"

PKGURL="https://github.com/zeromq/zeromq4-1/releases/download/v4.1.7/zeromq-4.1.7.tar.gz"
PKGDIR="zeromq-4.1.7"

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
# some tests fail occasionally.
$MAKE check
echo -n -e "\033]0;Build_Env: zeromq: make install\007"
$MAKE install

################################################################################
# Download and install OpenSSL
################################################################################
echo -n -e "\033]0;Build_Env: OpenSSL: download\007"

PKGURL="http://openssl.org/source/openssl-1.0.2u.tar.gz"
PKGDIR="openssl-1.0.2u"

download $PKGURL

echo "################################################################################"
echo "Building OpenSSL"
echo "################################################################################"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: OpenSSL: configure\007"
./Configure darwin64-x86_64-cc shared --prefix=$INSTALL_DIR --openssldir=$INSTALL_DIR/openssl
echo -n -e "\033]0;Build_Env: OpenSSL: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: OpenSSL: make test\007"
$MAKE test
echo -n -e "\033]0;Build_Env: OpenSSL: make install\007"
$MAKE install

################################################################################
# Download and install Python
################################################################################
echo -n -e "\033]0;Build_Env: Python: download\007"
# if $1 is true the we should remove the --enable-optimizations flag to get a quicker
# build if testing other functions of this script
if [ "$1" == "true" ]; then
    PY_CONF="--prefix=$INSTALL_DIR --enable-shared --with-ensurepip=install"
else
    PY_CONF="--prefix=$INSTALL_DIR --enable-shared --with-ensurepip=install --enable-optimizations"
fi
PKGURL="https://www.python.org/ftp/python/3.7.4/Python-3.7.4.tar.xz"
PKGDIR="Python-3.7.4"

download $PKGURL

echo "################################################################################"
echo "Building Python"
echo "################################################################################"
echo "Note there are some test failures"
cd $PKGDIR
echo -n -e "\033]0;Build_Env: Python: configure\007"
# removed --enable-toolbox-glue as no longer a config option
./configure $PY_CONF
echo -n -e "\033]0;Build_Env: Python: make\007"
$MAKE
echo -n -e "\033]0;Build_Env: Python: make install\007"
$MAKE install

################################################################################
# upgrade pip
################################################################################
$PIP install --upgrade pip wheel

################################################################################
# Download and install salt python dependencies
################################################################################
echo -n -e "\033]0;Build_Env: PIP Dependencies\007"

cd $BUILDDIR

echo "################################################################################"
echo "Installing Salt Dependencies with pip (normal)"
echo "################################################################################"
$PIP install -r $SRCDIR/requirements/static/pkg/py$PY_VERSION/darwin.txt \
             --target=$PYDIR/site-packages \
             --ignore-installed \
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
