#!/bin/bash
###############################################################################
#
# Title: Pre Install Script for Salt Installation
# Authors: Shane Lee
# Date: December 2015
#
# Description: This script stops the salt minion service before attempting to
#              install Salt on Mac OSX
#
# Requirements:
#    - None
#
# Usage:
#     This script is run as a part of the OSX Salt Installation
#
###############################################################################

###############################################################################
# Stop the service
###############################################################################
set -e
if /bin/launchctl list "com.saltstack.salt.minion" &> /dev/null; then
    /bin/launchctl unload "/Library/LaunchDaemons/com.saltstack.salt.minion.plist"
fi
