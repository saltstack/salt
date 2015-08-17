# Esky builds for SmartOS

This is intentionally currently not marked executable.
There are some hard coded bits, it depends on a binary copy of patchelf, etc.
However it does document pretty thoroughly how I initially created a build environment
for packaging up esky builds for SmartOS

```bash
#!/bin/bash

export PATH=$PATH:/opt/local/gcc47/bin/
HERE=$(pwd)

mv /opt/local /opt/local.backup ; hash -r
cd /
curl http://pkgsrc.joyent.com/packages/SmartOS/bootstrap/bootstrap-2014Q4-x86_64.tar.gz | gtar xz
hash -r

rm -rf /var/db/pkgin/
pkgin -y up
pkgin -y in build-essential salt swig py27-pip unzip py27-mysqldb libsodium mysql-client patchelf
pkgin -y rm salt py27-zmq

pip install --egg esky bbfreeze

cd $HERE
curl -kO 'https://pypi.python.org/packages/source/b/bbfreeze-loader/bbfreeze-loader-1.1.0.zip'
unzip bbfreeze-loader-1.1.0.zip

COMPILE="gcc -fno-strict-aliasing -O2 -pipe -O2 -DHAVE_DB_185_H -I/usr/include -I/opt/local/include -I/opt/local/include/db4 -I/opt/local/include/gettext -I/opt/local/include/ncurses -DNDEBUG -O2 -pipe -O2 -DHAVE_DB_185_H -I/usr/include -I/opt/local/include -I/opt/local/include/db4 -I/opt/local/include/gettext -I/opt/local/include/ncurses -fPIC -I/opt/local/include/python2.7 -static-libgcc"
$COMPILE -c bbfreeze-loader-1.1.0/_bbfreeze_loader/console.c -o $HERE/console.o
$COMPILE -c bbfreeze-loader-1.1.0/_bbfreeze_loader/getpath.c -o $HERE/getpath.o
gcc $HERE/console.o $HERE/getpath.o /opt/local/lib/python2.7/config/libpython2.7.a -L/opt/local/lib -L/opt/local/lib/python2.7/config -L/opt/local/lib -lsocket -lnsl -ldl -lrt -lm -static-libgcc -o $HERE/console.exe
patchelf --set-rpath '$ORIGIN:$ORIGIN/../lib' $HERE/console.exe

find /opt/local -name console.exe -exec mv $HERE/console.exe {} \;

git clone git://github.com/saltstack/salt -b 2014.7
cd $HERE/salt

# install all requirements
# (installing them as eggs seems to trigger esky pulling in the whole egg)
# this step is buggy... I had to run them repeatedly until they succeeded...
until pip install --egg -r pkg/smartos/esky/zeromq_requirements.txt ; do sleep 1 ; done ;
until pip install --egg -r pkg/smartos/esky/raet_requirements.txt ; do sleep 1 ; done ;

# install the sodium_grabber library
python2.7 pkg/smartos/esky/sodium_grabber_installer.py install

# ugly workaround for odd zeromq linking breakage
cp /opt/local/lib/libzmq.so.4 /opt/local/lib/python2.7/site-packages/pyzmq-13.1.0-py2.7-solaris-2.11-i86pc.64bit.egg/zmq/
patchelf --set-rpath '$ORIGIN:$ORIGIN/../lib' /opt/local/lib/python2.7/site-packages/pyzmq-13.1.0-py2.7-solaris-2.11-i86pc.64bit.egg/zmq/libzmq.so.4
cp /opt/local/lib/libsodium.so.13 /opt/local/lib/python2.7/site-packages/pyzmq-13.1.0-py2.7-solaris-2.11-i86pc.64bit.egg/zmq/
patchelf --set-rpath '$ORIGIN:$ORIGIN/../lib' /opt/local/lib/python2.7/site-packages/pyzmq-13.1.0-py2.7-solaris-2.11-i86pc.64bit.egg/zmq/libsodium.so.13

# at this point you have a build environment that you could set aside and reuse to run further builds.

bash pkg/smartos/esky/build-tarball.sh

# Upload packages into Manta
#mmkdir -p /$MANTA_USER/public/salt
#for file in dist/salt*; do mput -m /$MANTA_USER/public/salt -f $file; done;
```
