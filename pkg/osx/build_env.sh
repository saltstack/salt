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
#     - In order for the zeromq tests to pass we need to set the `maxfiles`
#       limits pretty high. Follow the instructions here:
#       https://superuser.com/a/1679740
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
#         ./build_env.sh
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

# Minimum Mac Version Supported
MACOSX_DEPLOYMENT_TARGET=10.15
export MACOSX_DEPLOYMENT_TARGET

# Versions we're going to install
PY_VERSION=3.9
PY_DOT_VERSION=3.9.12
ZMQ_VERSION=4.3.4
LIBSODIUM_VERSION=1.0.18

# Directories
SRC_DIR=`git rev-parse --show-toplevel`
SCRIPT_DIR=`pwd`
SHA_DIR=$SCRIPT_DIR/shasums
BUILD_DIR=$SCRIPT_DIR/build
INSTALL_DIR=/opt/salt
PYTHON_DIR=$INSTALL_DIR/lib/python$PY_VERSION
PIP=$INSTALL_DIR/bin/pip3
PYENV_INSTALL_DIR=~/pyenv

# Add pyenv to the path
export PATH=$PYENV_INSTALL_DIR/bin:$PATH

# Set PYENV_ROOT for the pyenv binary
export PYENV_ROOT=$INSTALL_DIR/.pyenv

################################################################################
# This is needed to allow some test suites (zmq) to pass
# taken from https://github.com/zeromq/libzmq/issues/1878
################################################################################
# Old Method
# SET_ULIMIT=300000
# sysctl -w kern.maxfiles=$SET_ULIMIT > /dev/null
# sysctl -w kern.maxfilesperproc=$SET_ULIMIT > /dev/null
# launchctl limit maxfiles $SET_ULIMIT $SET_ULIMIT
# ulimit -n 64000 $SET_ULIMIT

# To set the limits properly follow the instructions here:
# https://superuser.com/a/1679740
# Basically, create the file /Library/LaunchDaemons/limit.maxfiles.plist:
#<?xml version="1.0" encoding="UTF-8"?>
#<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
#<plist version="1.0">
#  <dict>
#    <key>Label</key>
#    <string>limit.maxfiles</string>
#    <key>ProgramArguments</key>
#    <array>
#      <string>launchctl</string>
#      <string>limit</string>
#      <string>maxfiles</string>
#      <string>524288</string>
#      <string>16777216</string>
#    </array>
#    <key>RunAtLoad</key>
#    <true/>
#    <key>ServiceIPC</key>
#    <false/>
#  </dict>
#</plist>

# Then Change Ownership:
# sudo chown root:wheel /Library/LaunchDaemons/limit.maxfiles.plist

# Load the Daemon:
# sudo launchctl load -w /Library/LaunchDaemons/limit.maxfiles.plist

# Finally, reboot the system to have the settings apply to ulimit -Sn/-Hn

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
    PKG_NAME=${URL##*/}

    cd $BUILD_DIR

    echo "**** Downloading $PKG_NAME"
    curl -LO# $URL

    echo "**** Comparing Sha512 Hash"
    FILE_SHA=($(shasum -a 512 $PKG_NAME))
    EXPECTED_SHA=($(cat $SHA_DIR/$PKG_NAME.sha512))
    if [ "$FILE_SHA" != "$EXPECTED_SHA" ]; then
        echo "ERROR: Sha Check Failed for $PKG_NAME"
        return 1
    fi

    echo "**** Unpacking $PKG_NAME"
    tar -zxvf $PKG_NAME

    return $?
}

################################################################################
# Ensure Paths are present and clean
################################################################################
echo "**** Ensure Paths are present and clean"

# Make sure $INSTALL_DIR is clean
echo "     - Install Dir"
rm -rf $INSTALL_DIR
mkdir -p $INSTALL_DIR
chown $USER:staff $INSTALL_DIR
mkdir -p $PYENV_ROOT

# Make sure build staging is clean
echo "     - Build Dir"
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Remove pyenv
echo "     - Pyenv Install Dir"
rm -rf $PYENV_INSTALL_DIR

################################################################################
# Download and install libsodium
################################################################################
echo "**** Download and install libsodium: $LIBSODIUM_VERSION"
echo -n -e "\033]0;Build_Env: libsodium $LIBSODIUM_VERSION: download\007"

PKG_URL="https://download.libsodium.org/libsodium/releases/libsodium-$LIBSODIUM_VERSION.tar.gz"
PKG_DIR="libsodium-$LIBSODIUM_VERSION"

download $PKG_URL

cd $PKG_DIR
echo -n -e "\033]0;Build_Env: libsodium $LIBSODIUM_VERSION: configure\007"
./configure --prefix=$PYENV_ROOT
echo -n -e "\033]0;Build_Env: libsodium: make\007"
$MAKE -j$(sysctl -n hw.ncpu)
echo -n -e "\033]0;Build_Env: libsodium: make check\007"
$MAKE check
echo -n -e "\033]0;Build_Env: libsodium: make install\007"
$MAKE install

################################################################################
# Download and install zeromq
################################################################################
echo "**** Downloading and installing zeromq: $ZMQ_VERSION"
echo -n -e "\033]0;Build_Env: zeromq $ZMQ_VERSION: download\007"

PKG_URL="https://github.com/zeromq/libzmq/releases/download/v$ZMQ_VERSION/zeromq-$ZMQ_VERSION.tar.gz"
PKG_DIR="zeromq-$ZMQ_VERSION"

download $PKG_URL

cd $PKG_DIR
echo -n -e "\033]0;Build_Env: zeromq $ZMQ_VERSION: configure\007"
./configure --prefix=$PYENV_ROOT
echo -n -e "\033]0;Build_Env: zeromq: make\007"
$MAKE -j$(sysctl -n hw.ncpu)
echo -n -e "\033]0;Build_Env: zeromq: make check\007"
# some tests fail occasionally.
$MAKE check
echo -n -e "\033]0;Build_Env: zeromq: make install\007"
$MAKE install

################################################################################
# Clone pyenv from github
################################################################################
echo "**** Clone pyenv repo"
echo -n -e "\033]0;Build_Env: pyenv\007"
cd ~
git clone https://github.com/pyenv/pyenv $PYENV_INSTALL_DIR

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
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/lib $INSTALL_DIR
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/bin $INSTALL_DIR
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/share $INSTALL_DIR
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/include $INSTALL_DIR
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/openssl $INSTALL_DIR
ln -s $PYENV_ROOT/versions/$PY_DOT_VERSION/readline $INSTALL_DIR

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

cd $BUILD_DIR

$PIP install -r $SRC_DIR/requirements/static/pkg/py$PY_VERSION/darwin.txt \
             --target=$PYTHON_DIR/site-packages \
             --ignore-installed \
             --upgrade \
             --no-cache-dir

cd $BUILD_DIR
echo -en "\033]0;\a"
echo "Build Environment Script Completed"
echo "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
