#!/bin/sh

# This is a generic wrapper for the salt-bootstrap script at:
#
# https://github.com/saltstack/salt-bootstrap
# 
# It has been designed as an example, to be customized for your own needs.

wget -O - http://bootstrap.saltstack.org | sudo sh
