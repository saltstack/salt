#!/bin/bash

echo '[salt]
Server = http://red45.org/archlinux
' >> /etc/pacman.conf
pacman -Syu --noconfirm salt
mkdir -p /etc/salt/pki
echo '{{ vm['priv_key'] }}' > /etc/salt/pki/minion.pem
echo '{{ vm['pub_key'] }}' > /etc/salt/pki/minion.pub
cat > /etc/salt/minion <<EOF
{{minion}}
EOF

/etc/rc.d/salt-minion start
