#!/bin/bash

pkgin -y in libtool-base autoconf automake libuuid gcc-compiler gmake

wget http://download.zeromq.org/zeromq-3.2.1-rc2.tar.gz
tar -xvf zeromq-3.2.1-rc2.tar.gz
cd zeromq-3.2.1
./configure
make
make install

pkgin -y in python27 py27-setuptools py27-yaml py27-crypto swig

# salt-cloud deps
#pkgin -y in gcc-compiler
#easy_install-2.7 paramiko
#easy_install-2.7 apache-libcloud

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
echo '{{ minion }}' > /etc/salt/minion

###
# TODO: Need to do the smartos version of chkconfig on
###
/opt/local/bin/salt-minion -d
