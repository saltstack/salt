#!/bin/bash

rpm -Uvh --force http://mirrors.kernel.org/fedora-epel/5/x86_64/epel-release-5-4.noarch.rpm
yum install -y salt-minion git
rm -rf /usr/lib/python2.6/site-packages/salt*
rm -rf /usr/bin/salt-*
mkdir -p /root/git
cd /root/git
git clone git://github.com/saltstack/salt.git
cd salt
python26 setup.py install
cd
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

/sbin/chkconfig salt-minion on
service salt-minion start
