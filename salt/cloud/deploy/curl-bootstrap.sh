#!/bin/sh
# bootstrap-salt <-- magic string needed to disguise as the salt-bootstrap script.
#
# This is a generic wrapper for the salt-bootstrap script at:
#
# https://github.com/saltstack/salt-bootstrap
#
# It has been designed as an example, to be customized for your own needs.

curl -L https://bootstrap.saltstack.com | sudo sh -s -- "$@"

# By default, Salt Cloud now places the minion's keys and configuration in
# /tmp/.saltcloud/ before executing the deploy script. After it has executed,
# these temporary files are removed. If you don't want salt-bootstrap to handle
# these files, comment out the above command, and uncomment the below command.

#curl -L https://bootstrap.saltstack.com | sudo sh
