#!/bin/bash

rpm -Uvh --force http://mirrors.kernel.org/fedora-epel/5/x86_64/epel-release-5-4.noarch.rpm
yum install -y salt-minion
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo '{{ minion }}' > /etc/salt/minion
/sbin/chkconfig salt-minion on
service salt-minion start
