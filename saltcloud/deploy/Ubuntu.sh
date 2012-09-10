#!/bin/bash

apt-get update
apt-get install -y python-software-properties
echo | add-apt-repository  ppa:saltstack/salt
apt-get update
apt-get install -y salt-minion
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo "{{ minion }}" > /etc/salt/minion
service salt-minion restart
