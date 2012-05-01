#!/bin/bash

rpm -Uvh http://mirrors.xmission.com/fedora/epel/6/i386/epel-release-6-5.noarch.rpm
yum install salt-minion
echo {{ priv_key }} > /etc/salt/pki/minion.pem
echo {{ pub_key }} > /etc/salt/pki/minion.pub
/sbin/chkconfig salt-minion on
service salt-minion start
