#!/bin/bash
################################################################################
#
# Title: Notarize Package Script for macOS
# Author: Shane Lee
# Date: December 2020
#
# Description: This notarizes the macOS Installer Package (.pkg). It uses the
#              `notarytool` xcode utility which became available in Xcode 13.
#              Xcode 13 requires macOS Big Sur 11.3 or higher. However, the
#              notarytool binary can be extracted and run on macOS Catalina
#              10.15.7 and higher. It is not available in Command Line Tools.
#
#              This script will upload a copy of the package to Apple and wait
#              for the notarization to return. This can take several minutes.
#
#              This script requires the presence of some environment variables.
#              If running this script with sudo, be sure to pass the `-E`
#              option.
#
#              sudo -E ./notarize.sh salt-3006.2-signed.pkg
#
# Requirements:
#     - Full Xcode Installation
#       I had issues installing Xcode after installing Command Line Tools. This
#       works better when it is a clean machine and only Xcode is installed.
#       The Xcode installation includes the Command Line Tools.
#
# Usage:
#     This script must be passed 1 parameter
#
#         $1 : <package>
#             The package that will be notarized (must be signed)
#
#     Example:
#         The following will notarize the 'salt-3006.2-signed.pkg' file:
#
#         ./notarize.sh salt-3006.2-signed.pkg
#
# Environment Setup:
#
#     Define Environment Variables:
#         Create three environment variables for the apple account, apple team
#         ID, and the app-specific password associated with that account. To
#         generate the app-specific password see:
#         https://support.apple.com/en-us/HT204397
#
#         export APPLE_ACCT="username@domain.com"
#         export APPLE_TEAM_ID="AB283DVDS5"
#         export APP_SPEC_PWD="abcd-efgh-ijkl-mnop"
#
################################################################################

#-------------------------------------------------------------------------------
# Check input parameters
#-------------------------------------------------------------------------------
if [ "$1" == "" ]; then
    echo "Must supply a package to notarize"
    exit 1
else
    PACKAGE=$1
fi

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _msg
#
#   Prints the message with a dash... no new line
_msg() {
    printf -- "- %s: " "$1"
}

# _success
#
#   Prints a green Success
_success() {
    printf "\e[32m%s\e[0m\n" "Success"
}

# _failure
#
#   Prints a red Failure and exits
_failure() {
    printf "\e[31m%s\e[0m\n" "Failure"
    echo "output >>>>>>"
    cat "$NOTARIZE_LOG" 1>&2
    echo "<<<<<< output"
    exit 1
}

#-------------------------------------------------------------------------------
# Environment Variables
#-------------------------------------------------------------------------------
_msg "Setting Variables"
NOTARIZE_LOG=$(mktemp -t notarize-app.log)
NOTARY_TOOL=$(xcrun --find notarytool)
_success

#-------------------------------------------------------------------------------
# Check for notarytool
#-------------------------------------------------------------------------------
if [ ! -f "$NOTARY_TOOL" ]; then
    echo "This script requires the NotaryTool binary"
    exit 1
fi

#-------------------------------------------------------------------------------
# Delete temporary files on exit
#-------------------------------------------------------------------------------
function finish {
    rm "$NOTARIZE_LOG"
}
trap finish EXIT

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Notarize Salt Package"
echo "- This can take up to 30 minutes"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Submit app for notarization
#-------------------------------------------------------------------------------
_msg "Submitting Package for Notarization"
if $NOTARY_TOOL submit \
        --apple-id "$APPLE_ACCT" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APP_SPEC_PWD" \
        --wait \
        "$PACKAGE" > "$NOTARIZE_LOG" 2>&1; then
    _success
else
    _failure
fi

# Make sure the status is "Accepted", then staple
_msg "Verifying accepted status"
if grep -q "status: Accepted" "$NOTARIZE_LOG"; then
    _success
else
    _failure
fi

_msg "Stapling Notarization to the Package"
if xcrun stapler staple "$PACKAGE" > "$NOTARIZE_LOG"; then
    _success
else
    _failure
fi

#-------------------------------------------------------------------------------
# Script Completed
#-------------------------------------------------------------------------------
printf -- "-%.0s" {1..80}; printf "\n"
echo "Notarize Salt Package Completed"
printf "=%.0s" {1..80}; printf "\n"
