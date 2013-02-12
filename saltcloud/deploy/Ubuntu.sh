#!/bin/bash

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo "{{ minion }}" > /etc/salt/minion

# add-apt-repository requires an additional dep and is in different packages
# on different systems. Although seemingly ubiquitous it is not a standard,
# and is only a convenience script intended to accomplish the below two steps 
# doing it this way is universal across all debian and ubuntu systems.
echo deb http://ppa.launchpad.net/saltstack/salt/ubuntu `lsb_release -sc` main | tee /etc/apt/sources.list.d/saltstack.list
wget -q -O- "http://keyserver.ubuntu.com:11371/pks/lookup?op=get&search=0x4759FA960E27C0A6" | apt-key add -

apt-get update
apt-get install -y -o DPkg::Options::=--force-confold salt-minion

# minion will be started automatically by install, except on Lucid
if [ `lsb_release -sc` = "lucid" ]; then
    pgrep -fl salt > /dev/null
    if [ "$?" = "1" ]; then
        sync
        start salt-minion
    fi
fi
