#!/bin/bash

############################################################################
#
# Title: Build Environment Script for OSX
# Authors: CR Oldham, Shane Lee
# Date: December 2015
#
# Description: This script sets up a build environment for salt on OSX.
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script is not passed any parameters
#
#     Example:
#         The following will set up a build environment for salt on OSX
#
#         ./dev_env.sh
#
############################################################################

trap 'quit_on_error $LINENO $BASH_COMMAND' ERR

quit_on_error() {
    echo "$(basename $0) caught error on line : $1 command was: $2"
    exit -1
}

############################################################################
# Parameters Required for the script to function properly
############################################################################

echo -n -e "\033]0;Build_Evn: Variables\007"

# This is needed to allow the some test suites (zmq) to pass
ulimit -n 1200

SRCDIR=`git rev-parse --show-toplevel`
SCRIPTDIR=`pwd`
PKG_CONFIG_PATH=/opt/salt/lib/pkgconfig
CFLAGS="-I/opt/salt/include"
LDFLAGS="-L/opt/salt/lib"

############################################################################
# Determine Which XCode is being used (XCode or XCode Command Line Tools)
############################################################################
# Prefer Xcode command line tools over any other gcc installed (e.g. MacPorts,
# Fink, Brew)
# Check for Xcode Commane Line Tools first
if [ -d '/Library/Developer/CommandLineTools/usr/bin' ]; then
    PATH=/Library/Developer/CommandLineTools/usr/bin:/opt/salt/bin:$PATH
    MAKE=/Library/Developer/CommandLineTools/usr/bin/make
else
    PATH=/Applications/Xcode.app/Contents/Developer/usr/bin:/opt/salt/bin:$PATH
    MAKE=/Applications/Xcode.app/Contents/Developer/usr/bin/make
fi
export PATH

############################################################################
# Ensure Paths are present and clean
############################################################################
echo -n -e "\033]0;Build_Evn: Clean\007"
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

echo -n -e "\033]0;Build_Evn: pkg-config\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving pkg-config"
echo "#####################################################################"
curl -O# http://repo.saltstack.com/osx/dependencies/pkg-config-0.29.tar.gz

echo "#####################################################################"
echo "Building pkg-config"
echo "#####################################################################"
tar -zxvf pkg-config-0.29.tar.gz
cd pkg-config-0.29
env LDFLAGS="-framework CoreFoundation -framework Carbon" ./configure --prefix=/opt/salt --with-internal-glib
$MAKE
$MAKE check
sudo $MAKE install


############################################################################
# Download and install libsodium
############################################################################

echo -n -e "\033]0;Build_Evn: libsodium\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving libsodium"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/libsodium-1.0.7.tar.gz

echo "#####################################################################"
echo "Building libsodium"
echo "#####################################################################"
tar -xvf libsodium-1.0.7.tar.gz
cd libsodium-1.0.7
./configure --prefix=/opt/salt
$MAKE
$MAKE check
sudo $MAKE install


############################################################################
# Download and install zeromq
############################################################################

echo -n -e "\033]0;Build_Evn: zeromq\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving zeromq"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/zeromq-4.1.3.tar.gz

echo "#####################################################################"
echo "Building zeromq"
echo "#####################################################################"
tar -zxvf zeromq-4.1.3.tar.gz
cd zeromq-4.1.3
./configure --prefix=/opt/salt
$MAKE
$MAKE check
sudo $MAKE install


############################################################################
# Download and install OpenSSL
############################################################################

echo -n -e "\033]0;Build_Evn: OpenSSL\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving OpenSSL 1.0.2e"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/openssl-1.0.2e.tar.gz

echo "#####################################################################"
echo "Building OpenSSL 1.0.2e"
echo "#####################################################################"
tar -zxvf openssl-1.0.2e.tar.gz
cd openssl-1.0.2e
./Configure darwin64-x86_64-cc --prefix=/opt/salt --openssldir=/opt/salt/openssl
$MAKE
$MAKE test
sudo $MAKE install


############################################################################
# Download and install GDBM
############################################################################

echo -n -e "\033]0;Build_Evn: GDBM\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving gdbm 1.11"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/gdbm-1.11.tar.gz

echo "#####################################################################"
echo "Building gdbm 1.11"
echo "#####################################################################"
tar -zxvf gdbm-1.11.tar.gz
cd gdbm-1.11
./configure --prefix=/opt/salt --enable-libgdbm-compat
$MAKE
$MAKE check
sudo $MAKE install


############################################################################
# Download and install Gnu Readline
############################################################################

echo -n -e "\033]0;Build_Evn: Gnu Readline\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving GNU Readline"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/readline-6.3.tar.gz

echo "#####################################################################"
echo "Building GNU Readline 6.3"
echo "#####################################################################"
tar -zxvf readline-6.3.tar.gz
cd readline-6.3
./configure --prefix=/opt/salt
$MAKE
sudo $MAKE install


############################################################################
# Download and install Python
############################################################################

echo -n -e "\033]0;Build_Evn: Python\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving Python 2.7.11"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/Python-2.7.11.tar.xz

echo "#####################################################################"
echo "Building Python 2.7.11"
echo "#####################################################################"
echo "Note there are some test failures"
tar -zxvf Python-2.7.11.tar.xz
cd Python-2.7.11
./configure --prefix=/opt/salt --enable-shared --enable-toolbox-glue --with-ensurepip=install
$MAKE
# $MAKE test
sudo $MAKE install


############################################################################
# Download and install CMake
############################################################################

echo -n -e "\033]0;Build_Evn: CMake\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving CMake 3.4.1"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/cmake-3.4.1.tar.gz

echo "#####################################################################"
echo "Building CMake 3.4.1"
echo "#####################################################################"
tar -zxvf cmake-3.4.1.tar.gz
cd cmake-3.4.1
./bootstrap
$MAKE
sudo $MAKE install


############################################################################
# Download and install libgit2
############################################################################

echo -n -e "\033]0;Build_Evn: libgit2\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Retrieving libgit2 0.23.4"
echo "#####################################################################"
curl -O# https://repo.saltstack.com/osx/dependencies/libgit2-0.23.4.tar.gz

echo "#####################################################################"
echo "Building libgit2 0.23.4"
echo "#####################################################################"
tar -zxvf libgit2-0.23.4.tar.gz
cd libgit2-0.23.4
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/opt/salt
sudo cmake --build . --target install


############################################################################
# Download and install salt python dependencies
############################################################################

echo -n -e "\033]0;Build_Evn: PIP Dependencies\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Installing Salt Dependencies with pip (normal)"
echo "#####################################################################"
sudo -H /opt/salt/bin/pip install \
                          -r $SRCDIR/pkg/osx/req.txt \
                          --no-cache-dir

echo "#####################################################################"
echo "Installing Salt Dependencies with pip (build_ext)"
echo "#####################################################################"
sudo -H /opt/salt/bin/pip install \
                          -r $SRCDIR/pkg/osx/req_ext.txt \
                          --global-option=build_ext \
                          --global-option="-I/opt/salt/include" \
                          --no-cache-dir

echo "---------------------------------------------------------------------"
echo "Create Symlink to certifi for openssl"
echo "---------------------------------------------------------------------"
ln -s /opt/salt/lib/python2.7/site-packages/certifi/cacert.pem /opt/salt/openssl/cert.pem

echo -n -e "\033]0;Build_Evn: Finished\007"

cd $BUILDDIR

echo "#####################################################################"
echo "Build Environment Script Completed"
echo "#####################################################################"
