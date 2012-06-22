#!/bin/bash

yum install -y salt-minion
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo '{{ minion }}' > /etc/salt/minion
systemctl enable salt-minion.service
systemctl start salt-minion.service
