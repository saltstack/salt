#!/bin/sh

# This is a generic wrapper for the salt-bootstrap script at:
#
# https://github.com/saltstack/salt-bootstrap
# 
# It has been designed as an example, to be customized for your own needs.

wget -O - http://bootstrap.saltstack.org | sudo sh -s -- -c /tmp

# Salt Cloud now places the minion's keys and configuration in /tmp/ before
# executing the deploy script. After it has executed, these temporary files
# are removed. If you don't want salt-bootstrap to handle these files, comment
# out the above line, and uncomment the below line.

#wget -O - http://bootstrap.saltstack.org | sudo sh
