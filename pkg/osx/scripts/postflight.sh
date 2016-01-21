#!/bin/bash
###############################################################################
#
# Title: Post Script for Salt Installation
# Authors: Shane Lee
# Date: December 2015
#
# Description: This script copies the minion config file and starts the salt
#              service
#
# Requirements:
#    - None
#
# Usage:
#     This script is run as a part of the OSX Salt Installation
#
###############################################################################

###############################################################################
# Check for existing minion config, copy if it doesn't exist
###############################################################################
if [ ! -f /etc/salt/minion ]; then
    cp /etc/salt/minion.dist /etc/salt/minion
fi

###############################################################################
# Register Salt as a service
###############################################################################
set -e
launchctl load "/Library/LaunchDaemons/com.saltstack.salt.minion.plist"
