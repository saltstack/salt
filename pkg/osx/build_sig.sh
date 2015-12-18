#!/bin/bash
############################################################################
#
# Title: Sign Package Script for OSX
# Authors: Shane Lee
# Date: December 2015
#
# Description: This signs an OSX Installer Package (.pkg)
#              /opt/salt
#
# Requirements:
#     - XCode Command Line Tools (xcode-select --install)
#     - A valid signing certificate in the login.keychain. Signing Certificates
#       can be optained from the Apple Developer site.
#
# Usage:
#     This script must be passed 2 parameters
#         $1 : <source package> : the package that will be signed
#         $2 : <signed package> : the name to give the signed package (can't be
#              the same as the source package)
#
#     Example:
#         The following will sign the 'salt-v2015.8.3.pkg' file and save it as
#         'salt-v2015.8.3.signed.pkg'
#
#         ./build_sig.sh salt-v2015.8.3.pkg salt-v2015.8.3.signed.pkg
#
############################################################################

############################################################################
# Check input parameters
############################################################################
if [ "$1" == "" ]; then
    echo "Must supply an source package"
else
    INPUT=$1
fi

if [ "$2" == "" ]; then
    echo "Must supply an signed package name"
else
    OUTPUT=$2
fi

############################################################################
# Import the Salt Developer Signing certificate
############################################################################
security import "Developer ID Installer.p12" -k ~/Library/Keychains/login.keychain

############################################################################
# Signe the package
############################################################################
productsign --sign "Developer ID Installer: Salt Stack, Inc. (VK797BMMY4)" $INPUT $OUTPUT
