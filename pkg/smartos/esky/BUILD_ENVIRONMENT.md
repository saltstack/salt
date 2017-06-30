# Esky builds for SmartOS

This is intentionally currently not marked executable.
There are some hard coded bits, it depends on a binary copy of patchelf, etc.
However it does document pretty thoroughly how I initially created a build environment
for packaging up esky builds for SmartOS

```bash
#!/bin/sh
set -ux

## environment
export PATH=$PATH:/opt/local/gcc49/bin/
BLDPATH=/tmp/bbfreeze_loader
SALTBASE=/data

## packages
pkgin -y in build-essential salt swig py27-pip unzip py27-mysqldb libsodium mysql-client patchelf
pkgin -y rm salt py27-zmq

pip install --no-use-wheel --egg esky bbfreeze

## bzfreeze-loader
COMPILE="gcc -fno-strict-aliasing -O2 -pipe -DHAVE_DB_185_H -I/usr/include -I/opt/local/include -I/opt/local/include/db4 -I/opt/local/include/gettext -I/opt/local/include/ncurses -DNDEBUG -fPIC -I/opt/local/include/python2.7 -static-libgcc"
LINK_OPTS="-L/opt/local/lib -L/opt/local/lib/python2.7/config -lsocket -lnsl -ldl -lrt -lm -lssp -static-libgcc"
mkdir -p ${BLDPATH}
cd ${BLDPATH}
curl -kO 'https://pypi.python.org/packages/source/b/bbfreeze-loader/bbfreeze-loader-1.1.0.zip'
unzip bbfreeze-loader-1.1.0.zip
${COMPILE} -c bbfreeze-loader-1.1.0/_bbfreeze_loader/console.c -o ${BLDPATH}/console.o
${COMPILE} -c bbfreeze-loader-1.1.0/_bbfreeze_loader/getpath.c -o ${BLDPATH}/getpath.o
gcc ${BLDPATH}/console.o ${BLDPATH}/getpath.o /opt/local/lib/python2.7/config/libpython2.7.a ${LINK_OPTS} -o ${BLDPATH}/console.exe
find /opt/local -name console.exe -exec cp ${BLDPATH}/console.exe {} \;

## clone saltstack repo
cd ${SALTBASE}
git clone git://github.com/saltstack/salt -b 2016.11

## salt requirements
cd ${SALTBASE}/salt
until pip install --no-use-wheel --egg -r pkg/smartos/esky/zeromq_requirements.txt ; do sleep 1 ; done ;
until pip install --no-use-wheel --egg -r pkg/smartos/esky/raet_requirements.txt ; do sleep 1 ; done ;

## sodium grabber
cd ${SALTBASE}/salt
python2.7 pkg/smartos/esky/sodium_grabber_installer.py install

## cleanup
rm -r ${BLDPATH}

## build esky package
cd ${SALTBASE}/salt
pkg/smartos/esky/build-tarball.sh
```
