#!/bin/sh

portsnap fetch extract update
cd /usr/ports/ports-mgmt/pkg
make install clean
cd
/usr/local/sbin/pkg2ng
echo 'PACKAGESITE: http://pkgbeta.freebsd.org/freebsd-9-amd64/latest' > /usr/local/etc/pkg.conf
pkg install -y salt
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo '{{ minion }}' > /etc/salt/minion
salt-minion -d
