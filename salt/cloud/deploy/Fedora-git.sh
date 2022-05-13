#!/bin/bash

# This legacy script pre-dates the salt-bootstrap project. In most cases, the
# bootstrap-salt.sh script is the recommended script for installing salt onto
# a new minion. However, that may not be appropriate for all situations. This
# script remains to help fill those needs, and to provide an example for users
# needing to write their own deploy scripts.

# Install the salt-minion package from yum. This is easy for Fedora because
# Salt packages are in the Fedora package repos
yum install -y salt-minion git
echo 'Installed Salt'
rm -rf /usr/lib/python/site-packages/salt*
rm -rf /usr/bin/salt-*
mkdir -p /root/git
cd /root/git
git clone git://github.com/saltstack/salt.git
cd salt
python setup.py install
cd
# Save in the minion public and private RSA keys before the minion is started
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
# Copy the minion configuration file into place before starting the minion
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

# Set the minion to start on reboot
systemctl enable salt-minion.service
# Start the minion!
systemctl start salt-minion.service
