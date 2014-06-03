#!/bin/bash
PKG_DIR=$(cd $(dirname $0); pwd)
BUILD_DIR=build/output/salt

rm -rf dist/ $BUILD_DIR &&\
cp $PKG_DIR/_syspaths.py salt/ &&\
python2.7 setup.py bdist &&\
python2.7 setup.py bdist_esky &&\
rm salt/_syspaths.py &&\
rm -f dist/*.tar.gz &&\
mkdir -p $BUILD_DIR/{etc,install,bin/appdata} &&\
cp conf/* $BUILD_DIR/etc/
cp $PKG_DIR/*.xml $PKG_DIR/install.sh $BUILD_DIR/install &&\
chmod +x $BUILD_DIR/install/install.sh &&\
unzip -d $BUILD_DIR/bin dist/*.zip &&\
cp $BUILD_DIR/bin/*/libgcc_s.so.1 $BUILD_DIR/bin/ &&\
find build/output/salt/bin/ -mindepth 1 -maxdepth 1 -type d -not -name appdata -exec mv {} $BUILD_DIR/bin/appdata/ \; &&\
gtar -C $BUILD_DIR/.. -czvf dist/salt-$(git describe | sed 's|^v||')-esky-smartos.tar.gz salt &&\
echo "tarball built"
