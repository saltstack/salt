#!/bin/bash

# This legacy script pre-dates the salt-bootstrap project. In most cases, the
# bootstrap-salt.sh script is the recommended script for installing salt onto
# a new minion. However, that may not be appropriate for all situations. This
# script remains to help fill those needs, and to provide an example for users
# needing to write their own deploy scripts.

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

# echo deb http://ftp.debian.org/debian experimental main | tee -a /etc/apt/sources.list
echo deb http://backports.debian.org/debian-backports squeeze-backports main | tee -a /etc/apt/sources.list
echo deb http://debian.madduck.net/repo squeeze-backports main | tee -a /etc/apt/sources.list
wget -q -O- "http://debian.madduck.net/repo/gpg/archive.key" | apt-key add -

apt-get update
apt-get install -y -o DPkg::Options::=--force-confold salt-minion
# minion will be started automatically by install
