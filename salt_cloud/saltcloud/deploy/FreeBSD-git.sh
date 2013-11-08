#!/bin/sh

portsnap fetch extract update
cd /usr/ports/ports-mgmt/pkg
make install clean
cd
/usr/local/sbin/pkg2ng
echo 'PACKAGESITE: http://pkgbeta.freebsd.org/freebsd-9-amd64/latest' > /usr/local/etc/pkg.conf
/usr/local/sbin/pkg install -y git salt
/usr/local/sbin/pkg delete -y salt
mkdir -p /root/git
cd /root/git
/usr/local/bin/git clone git://github.com/saltstack/salt.git
cd salt
/usr/local/bin/python setup.py install
cd
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /usr/local/etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /usr/local/etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

salt-minion -d
