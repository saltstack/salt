#!/bin/bash

# Usage
# ./build.sh <package dir> <version to build> <git tag>

SRCDIR=`pwd`

if [[ ! -e "$SRCDIR/.git" ]] && [[ ! -e "$SRCDIR/scripts/salt" ]]; then
    echo "This directory doesn't appear to be a git repository."
    echo "The OS X build process needs some files from a Git checkout of Salt."
    echo "Run this script from the root of the Git checkout."
    exit -1
fi

PKGDIR=$1

mkdir -p build
BUILDDIR=`pwd`/build

PKGRESOURCES=$SRCDIR/pkg/osx

mkdir -p /opt/salt

virtualenv /opt/salt
source /opt/salt/bin/activate

cd $BUILDDIR

echo "-------- Retrieving libsodium"
wget https://download.libsodium.org/libsodium/releases/libsodium-1.0.2.tar.gz
wget https://download.libsodium.org/libsodium/releases/libsodium-1.0.2.tar.gz.sig

echo "-------- Verifying PGP signature"
gpg --keyserver pgp.mit.edu --recv-key 2B6F76DA
gpg --verify libsodium-1.0.2.tar.gz.sig

echo "-------- Building libsodium"
tar -xvf libsodium-1.0.2.tar.gz
cd libsodium-1.0.2
./configure --prefix=/opt/salt
make
make check
make install

cd $BUILDDIR

echo "-------- Retrieving zeromq"
wget http://download.zeromq.org/zeromq-4.0.5.tar.gz
wget http://download.zeromq.org/SHA1SUMS

echo "-------- Building zeromq"
tar -zxvf zeromq-4.0.5.tar.gz
cd zeromq-4.0.5
./configure --prefix=/opt/salt
make
make check
make install

cd $BUILDDIR

echo "-------- Retrieving SWIG 3.0.4"
# SWIG
wget http://downloads.sourceforge.net/project/swig/swig/swig-3.0.4/swig-3.0.4.tar.gz

echo "-------- Building SWIG 3.0.4"
tar -zxvf swig-3.0.4.tar.gz
cd swig-3.0.4
./configure --prefix=/opt/salt
make
make install


echo "-------- Installing Salt dependencies with pip"
pip install -r $PKGRESOURCES/requirements.txt

# if $3 exists it will be a git reference, install with pip install git+
# otherwise install with pip install salt==
echo "-------- Installing Salt into the virtualenv"
if [ "$3" == "" ]; then
    pip install salt==$2
else
    pip install $3
fi

cd /opt/salt/bin
rm python
ln -s /usr/bin/python
# sed -i '' 's/^#!\/.*/#!\/opt\/salt\/bin\/python/g' $1/opt/salt/bin/salt* $1/opt/salt/bin/pip* $1/opt/salt/bin/ioflo* $1/opt/salt/bin/easy_install $1/opt/salt/bin/raetflo

# mv salt salt.py
# mv salt-master salt-master.py
# mv salt-minion salt-minion.py
# mv salt-api salt-api.py
# mv salt-cloud salt-cloud.py
# mv salt-unity salt-unity.py
# cp $PKGRESOURCES/scripts/salt* .

# sed -i '' 's/VIRTUAL_ENV=.*/VIRTUAL_ENV=\/opt\/salt/g' $1/opt/salt/bin/activate
# rm $1/opt/salt/bin/activate.csh
# rm $1/opt/salt/bin/activate.fish

cp $PKGRESOURCES/scripts/start-*.sh /opt/salt/bin

mkdir -p $PKGDIR/opt
cp -r /opt/salt $PKGDIR/opt

mkdir -p $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.minion.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.master.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.syndic.plist $PKGDIR/Library/LaunchDaemons
cp $PKGRESOURCES/scripts/com.saltstack.salt.api.plist $PKGDIR/Library/LaunchDaemons

mkdir -p $PKGDIR/etc/salt
cp $SRCDIR/conf/minion $PKGDIR/etc/salt/minion.dist
cp $SRCDIR/Users/cro/src/ve/sd/salt/conf/master $PKGDIR/etc/salt/master.dist

cd $PKGRESOURCES
cp distribution.xml.dist distribution.xml
SEDSTR="s/@VERSION@/$2/"
echo $SEDSTR
sed -i '' $SEDSTR distribution.xml

pkgbuild --root $PKGDIR --identifier=com.saltstack.salt --version=$2 --ownership=recommended salt-src-$2.pkg
productbuild --distribution=distribution.xml --package-path=salt-src-$2.pkg --version=$2 salt-$2.pkg


# copy the wrapper script to /opt/salt/bin
# ln -s all the different wrapper names to that script
# Copy the launchd plists to $1/Library/LaunchDaemons
# Copy the sample config files to $1/etc

# pkgbuild and productbuild will use $2 to name files.

#pkgbuild

#productbuild

# Q.E.D.


