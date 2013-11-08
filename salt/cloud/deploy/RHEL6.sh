#!/bin/bash

rpm -Uvh --force http://mirrors.kernel.org/fedora-epel/6/x86_64/epel-release-6-8.noarch.rpm
yum -y install salt-minion --enablerepo epel-testing
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

/sbin/chkconfig salt-minion on
service salt-minion start
