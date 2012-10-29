#!/bin/bash

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo "{{ minion }}" > /etc/salt/minion

apt-get update
apt-get install -y python-software-properties
echo | add-apt-repository  ppa:saltstack/salt
apt-get update
apt-get install -y salt-minion git-core
rm -rf /usr/share/pyshared/salt*
rm -rf /usr/bin/salt-*
mkdir -p /root/git
cd /root/git
git clone git://github.com/saltstack/salt.git
cd salt
python setup.py install --install-layout=deb
service salt-minion start
