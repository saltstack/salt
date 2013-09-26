#!/bin/bash

pkgin -y in libtool-base autoconf automake libuuid gcc-compiler gmake python27 py27-setuptools py27-yaml py27-crypto swig

wget http://download.zeromq.org/zeromq-3.2.1-rc2.tar.gz
tar -xvf zeromq-3.2.1-rc2.tar.gz
cd zeromq-3.2.1
./configure
make
make install

easy_install-2.7 pyzmq
easy_install-2.7 salt

mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

###
# TODO: * create /opt/local/share/smf/salt-minion/manifest.xml in salt.git
#       * svcadm enable salt-minion
#       * remove line below
###
/opt/local/bin/salt-minion -d
