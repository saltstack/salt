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
curl http://pkgsrc.joyent.com/packages/SmartOS/bootstrap/bootstrap-2013Q3-x86_64.tar.gz | gtar xz
hash -r

pkgin -y up
pkgin -y in build-essential salt swig py27-pip unzip 
pkgin -y rm salt

cd /opt/local/bin
curl -kO 'https://us-east.manta.joyent.com/nahamu/public/smartos/bins/patchelf'
chmod +x patchelf
cat >swig <<"EOF"
#!/bin/bash
exec /opt/local/bin/swig2.0 -I/opt/local/include "$@"
EOF

pip install esky
yes | pip uninstall bbfreeze

cd $HERE
curl -kO 'https://pypi.python.org/packages/source/b/bbfreeze-loader/bbfreeze-loader-1.1.0.zip'
unzip bbfreeze-loader-1.1.0.zip

COMPILE="gcc -fno-strict-aliasing -O2 -pipe -O2 -DHAVE_DB_185_H -I/usr/include -I/opt/local/include -I/opt/local/include/db4 -I/opt/local/include/gettext -I/opt/local/include/ncurses -DNDEBUG -O2 -pipe -O2 -DHAVE_DB_185_H -I/usr/include -I/opt/local/include -I/opt/local/include/db4 -I/opt/local/include/gettext -I/opt/local/include/ncurses -fPIC -I/opt/local/include/python2.7 -static-libgcc"
$COMPILE -c bbfreeze-loader-1.1.0/_bbfreeze_loader/console.c -o $HERE/console.o
$COMPILE -c bbfreeze-loader-1.1.0/_bbfreeze_loader/getpath.c -o $HERE/getpath.o
gcc $HERE/console.o $HERE/getpath.o /opt/local/lib/python2.7/config/libpython2.7.a -L/opt/local/lib -L/opt/local/lib/python2.7/config -L/opt/local/lib -lsocket -lnsl -ldl -lrt -lm -static-libgcc -o $HERE/console.exe
patchelf --set-rpath '$ORIGIN:$ORIGIN/../lib' $HERE/console.exe

git clone git://github.com/schmir/bbfreeze -b master
( cd $HERE/bbfreeze && easy_install-2.7 . )
find /opt/local -name console.exe -exec mv $HERE/console.exe {} \;

git clone git://github.com/saltstack/salt -b 0.17
( cd $HERE/salt && python2.7 setup.py bdist && python2.7 setup.py bdist_esky )

mv /opt/local /opt/local.build ; hash -r
mv /opt/local.backup /opt/local ; hash -r

mmkdir -p /$MANTA_USER/public/salt
mput /$MANTA_USER/public/salt -f $(ls salt/dist/*.zip)
```
