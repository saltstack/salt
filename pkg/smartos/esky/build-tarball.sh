#!/bin/bash

set -o errexit

PKG_DIR=$(cd $(dirname $0); pwd)
BUILD_DIR=build/output/salt

# In case this is a git checkout, run sdist then extract out tarball
# contents to get all the critical versioning files into place
rm -rf dist/
python2.7 setup.py sdist
gtar xzvf dist/salt*.tar.gz --strip-components=1

rm -rf dist/ $BUILD_DIR
cp $PKG_DIR/_syspaths.py salt/
python2.7 setup.py bdist
python2.7 setup.py bdist_esky
rm salt/_syspaths.py
rm -f dist/*.tar.gz
mkdir -p $BUILD_DIR/{bin/appdata,install,var/log/salt}
cp -r conf $BUILD_DIR/etc
cp $PKG_DIR/*.xml $PKG_DIR/install.sh $BUILD_DIR/install
chmod +x $BUILD_DIR/install/install.sh
unzip -d $BUILD_DIR/bin dist/*.zip
cp $BUILD_DIR/bin/*/libgcc_s.so.1 $BUILD_DIR/bin/
cp $BUILD_DIR/bin/*/libssp.so.0 $BUILD_DIR/bin/
find build/output/salt/bin/ -mindepth 1 -maxdepth 1 -type d -not -name appdata -exec mv {} $BUILD_DIR/bin/appdata/ \;
PYZMQ=$(find ${BUILD_DIR}/bin/ -mindepth 1 -type d -name 'pyzmq-*.egg')/zmq
find /opt/local/lib/ -maxdepth 1 -type l -regextype sed -regex '.*/libzmq.so.[0-9]\+$' -exec cp {} ${PYZMQ}/ \;
find /opt/local/lib/ -maxdepth 1 -type l -regextype sed -regex '.*/libsodium.so.[0-9]\+$' -exec cp {} ${PYZMQ}/ \;
find ${PYZMQ}/ -maxdepth 1 -type f -name '*.so.*' -exec patchelf --set-rpath '$ORIGIN:$ORIGIN/../../:$ORIGIN/../lib' {} \;
find ${PYZMQ}/ -maxdepth 1 -type f -name '*.so.*' -exec cp {} ${PYZMQ}/../../ \;
find ${PYZMQ}/ -maxdepth 3 -type f -name '*.so' -exec patchelf --set-rpath '$ORIGIN:$ORIGIN/../../:$ORIGIN/../lib:$ORIGIN/../../../../' {} \;
gtar -C $BUILD_DIR/.. -czvf dist/salt-$(awk '/^Version:/{print $2}' < PKG-INFO)-esky-smartos.tar.gz salt
echo "tarball built"
