#!/bin/bash

# This legacy script pre-dates the salt-bootstrap project. In most cases, the
# bootstrap-salt.sh script is the recommended script for installing salt onto
# a new minion. However, that may not be appropriate for all situations. This
# script remains to help fill those needs, and to provide an example for users
# needing to write their own deploy scripts.

echo '[salt]
Server = http://red45.org/archlinux
' >> /etc/pacman.conf
pacman -Syu --noconfirm salt git
rm -rf /usr/lib/python2.7/site-packages/salt*
rm -rf /usr/bin/salt-*
mkdir -p /root/git
cd /root/git
git clone git://github.com/saltstack/salt.git
cd salt
python2 setup.py install
cd
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

/etc/rc.d/salt-minion start
