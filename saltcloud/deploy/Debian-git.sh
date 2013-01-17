#!/bin/bash

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo "{{ minion }}" > /etc/salt/minion

# echo deb http://ftp.debian.org/debian experimental main | tee -a /etc/apt/sources.list
echo deb http://backports.debian.org/debian-backports squeeze-backports main | tee -a /etc/apt/sources.list
echo deb http://debian.madduck.net/repo squeeze-backports main | tee -a /etc/apt/sources.list
wget -q -O- "http://debian.madduck.net/repo/gpg/archive.key" | apt-key add -

apt-get update
apt-get install -y -o DPkg::Options::=--force-confold salt-minion git-core
# minion will be started automatically by install
service salt-minion stop

rm -rf /usr/share/pyshared/salt*
rm -rf /usr/bin/salt-*
mkdir -p /root/git
cd /root/git
git clone git://github.com/saltstack/salt.git
cd salt
python setup.py install --install-layout=deb
service salt-minion start
