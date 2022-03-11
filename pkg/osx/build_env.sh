#!/bin/bash
################################################################################
#
# Title: Build Environment Script for macOS
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script sets up a build environment for Salt on macOS using
#              pyenv.
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script can be passed 1 parameter
#       $1 : <test mode> :   If this script is run in test mode, python is not
#                            optimized when it is built. Please DO NOT set to
#                            "true" when building a release version.
#                            (default is false)
#
#     Example:
#         The following will set up an optimized Python build environment for
#         Salt on macOS
#
#         ./dev_env.sh
#
################################################################################

echo "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
echo "Build Environment Script"

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
    echo -en "\033]0;\a"
    exit 1
}

################################################################################
# Parameters Required for the script to function properly
################################################################################
echo "**** Setting Variables"

MACOSX_DEPLOYMENT_TARGET=10.15
export MACOSX_DEPLOYMENT_TARGET

# This is needed to allow the some test suites (zmq) to pass
# taken from https://github.com/zeromq/libzmq/issues/1878
SET_ULIMIT=300000
sysctl -w kern.maxfiles=$SET_ULIMIT > /dev/null
sysctl -w kern.maxfilesperproc=$SET_ULIMIT > /dev/null
launchctl limit maxfiles $SET_ULIMIT $SET_ULIMIT
ulimit -n 64000 $SET_ULIMIT

PY_VERSION=3.7
PY_DOT_VERSION=3.7.12
ZMQ_VERSION=4.3.4
LIBSODIUM_VERSION=1.0.18
SRCDIR=`git rev-parse --show-toplevel`
SCRIPTDIR=`pwd`
SHADIR=$SCRIPTDIR/shasums
INSTALL_DIR=/opt/salt
PYDIR=$INSTALL_DIR/lib/python$PY_VERSION
PYTHON=$INSTALL_DIR/bin/python3
PIP=$INSTALL_DIR/bin/pip3

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
    exit 1
fi
echo "**** Using make from: $MAKE"

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

    echo "**** Retrieving $PKGNAME"
    curl -LO# $URL

    echo "**** Comparing Sha512 Hash"
    FILESHA=($(shasum -a 512 $PKGNAME))
    EXPECTEDSHA=($(cat $SHADIR/$PKGNAME.sha512))
    if [ "$FILESHA" != "$EXPECTEDSHA" ]; then
        echo "ERROR: Sha Check Failed for $PKGNAME"
        return 1
    fi

    echo "**** Unpacking $PKGNAME"
    tar -zxvf $PKGNAME

    return $?
}

################################################################################
# Ensure Paths are present and clean
################################################################################
echo "**** Ensure Paths are present and clean"

# Make sure $INSTALL_DIR is clean
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR
chown $USER:staff $INSTALL_DIR

# Make sure build staging is clean
rm -rf build
mkdir -p build
BUILDDIR=$SCRIPTDIR/build

################################################################################
# Clone pyenv from github
################################################################################
echo "**** Clone pyenv repo"
echo -n -e "\033]0;Build_Env: pyenv\007"
cd ~
mkdir -p /opt/salt
git clone https://github.com/pyenv/pyenv /opt/salt/.pyenv
export PYENV_ROOT=/opt/salt/.pyenv
export PATH=/opt/salt/.pyenv/bin:$PATH

################################################################################
# Use pyenv to install Python
################################################################################
echo "**** Use pyenv to install Python $PY_DOT_VERSION"
echo -n -e "\033]0;Build_Env: Use pyenv to install Python $PY_DOT_VERSION\007"
if [ "$1" != "true" ]; then
    export PYTHON_CONFIGURE_OPTS="--enable-optimizations"
else
    unset PYTHON_CONFIGURE_OPTS
fi
pyenv install $PY_DOT_VERSION

################################################################################
# Softlink the pyenv versions/$PY_DOT_VERSION directories
################################################################################
echo "**** Create softlinks to pyenv versions $PY_DOT_VERSION directories"
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/lib /opt/salt
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/bin /opt/salt
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/share /opt/salt
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/include /opt/salt
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/openssl /opt/salt
ln -s /opt/salt/.pyenv/versions/$PY_DOT_VERSION/readline /opt/salt

################################################################################
# Download and install libsodium
################################################################################
echo "**** Download and install libsodium: $LIBSODIUM_VERSION"
echo -n -e "\033]0;Build_Env: libsodium $LIBSODIUM_VERSION: download\007"

PKGURL="https://download.libsodium.org/libsodium/releases/libsodium-$LIBSODIUM_VERSION.tar.gz"
PKGDIR="libsodium-$LIBSODIUM_VERSION"

download $PKGURL

cd $PKGDIR
echo -n -e "\033]0;Build_Env: libsodium $LIBSODIUM_VERSION: configure\007"
./configure --prefix=$PYENV_ROOT
echo -n -e "\033]0;Build_Env: libsodium: make\007"
$MAKE -j4
echo -n -e "\033]0;Build_Env: libsodium: make check\007"
$MAKE check
echo -n -e "\033]0;Build_Env: libsodium: make install\007"
$MAKE install

################################################################################
# Download and install zeromq
################################################################################
echo "**** Downloading and installing zeromq: $ZMQ_VERSION"
echo -n -e "\033]0;Build_Env: zeromq $ZMQ_VERSION: download\007"

PKGURL="https://github.com/zeromq/libzmq/releases/download/v$ZMQ_VERSION/zeromq-$ZMQ_VERSION.tar.gz"
PKGDIR="zeromq-$ZMQ_VERSION"

download $PKGURL

cd $PKGDIR
echo -n -e "\033]0;Build_Env: zeromq $ZMQ_VERSION: configure\007"
./configure --prefix=$INSTALL_DIR
echo -n -e "\033]0;Build_Env: zeromq: make\007"
$MAKE -j4
echo -n -e "\033]0;Build_Env: zeromq: make check\007"
# some tests fail occasionally.
$MAKE check
echo -n -e "\033]0;Build_Env: zeromq: make install\007"
$MAKE install

################################################################################
# upgrade pip
################################################################################
echo "**** Upgrading pip and wheel"
$PIP install --upgrade pip wheel

################################################################################
# Download and install salt python dependencies
################################################################################
echo "**** Installing Salt Dependencies with pip (normal)"
echo -n -e "\033]0;Build_Env: PIP Dependencies\007"

cd $BUILDDIR

$PIP install -r $SRCDIR/requirements/static/pkg/py$PY_VERSION/darwin.txt \
             --target=$PYDIR/site-packages \
             --ignore-installed \
             --upgrade \
             --no-cache-dir

cd $BUILDDIR
echo -en "\033]0;\a"
echo "Build Environment Script Completed"
echo "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
