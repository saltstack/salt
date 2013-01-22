#!/bin/bash

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo "{{ minion }}" > /etc/salt/minion

apt-get install -y python-software-properties
#Add simulated [enter] key to add-apt-repository
echo | add-apt-repository -y ppa:saltstack/salt
apt-get update

apt-get install -y -o DPkg::Options::=--force-confold salt-minion
# minion will be started automatically by install
