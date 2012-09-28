#!/bin/bash

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
echo '{{ minion }}' > /etc/salt/minion
/etc/rc.d/salt-minion start
