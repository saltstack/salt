#!/bin/sh

HERE=$(dirname $0)
TOP=$(cd $HERE/.. ; pwd)

mkdir $HERE/output
for file in $HERE/*.xml
do
  sed "s#SALT_PREFIX#$TOP#" <$file >$HERE/output/$(basename $file)
  svccfg import $HERE/output/$(basename $file)
done
rm -rf $HERE/output

echo "To enable services, invoke any of"
echo "    svcadm enable salt-minion"
echo "    svcadm enable salt-master"
echo "    svcadm enable salt-syndic"
echo "as appropriate"
