#!/bin/bash
################################################################################
#
# Title: Notarize Package Script for macOS
# Author: Shane Lee
# Date: December 2020
#
# Description: This notarizes the macOS Installer Package (.pkg). It uses the
#              `altool` xcode utility which is only available in the full
#              Xcode package. It is not available in Command Line Tools.
#
#              This script will upload a copy of the package to apple and wait
#              for the notarization to return. This can take several minutes.
#
#              This script should be run with sudo. If not, it will attempt to
#              elevate and run with sudo. In order for the environment variables
#              to be available in sudo you need to pass the `-E` option. For
#              example:
#
#              sudo -E ./notarize.sh
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
#         The following will notarize the 'salt-v2015.8.3-signed.pkg' file
#
#         sudo ./notarize.sh salt-v2015.8.3-signed.pkg
#
# Environment Setup:
#
#     Define Environment Variables:
#         Create two environment variables for the apple account and the
#         app-specific password associated with that account. To generate the
#         app-specific password see: https://support.apple.com/en-us/HT204397
#
#         export APPLE_ACCT="username@domain.com"
#         export APP_SPEC_PWD="abcd-efgh-ijkl-mnop"
#
################################################################################
echo "vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv"
echo "Notarize Salt Package"

# Make sure the script is launched with sudo
# We're doing this with notarize because the package we're notarizing was
# built with sudo... so, we need sudo here in order to staple the notarization
# to the package
if [[ $(id -u) -ne 0 ]]; then
    echo ">>>>>> Re-launching as sudo <<<<<<"
    exec sudo -E /bin/bash -c "$(printf '%q ' "${BASH_SOURCE[0]}" "$@")"
fi

################################################################################
# Check input parameters
################################################################################
if [ "$1" == "" ]; then
    echo "Must supply a package to notarize"
    exit 1
else
    PACKAGE=$1
fi

################################################################################
# Environment Variables
################################################################################
echo "**** Setting Variables"
BUNDLE_ID="com.saltstack.salt"
NOTARIZE_APP_LOG=$(mktemp -t notarize-app)
NOTARIZE_INFO_LOG=$(mktemp -t notarize-info)

################################################################################
# Delete temporary files on exit
################################################################################
function finish {
    rm "$NOTARIZE_APP_LOG" "$NOTARIZE_INFO_LOG"
}
trap finish EXIT

################################################################################
# Submit app for notarization
################################################################################
echo "**** Submitting Package for Notarization"
if ! xcrun altool --notarize-app \
                  --primary-bundle-id "$BUNDLE_ID" \
                  --username "$APPLE_ACCT" \
                  --password "$APP_SPEC_PWD" \
                  -f "$PACKAGE" > "$NOTARIZE_APP_LOG" 2>&1; then
    cat "$NOTARIZE_APP_LOG" 1>&2
    exit 1
fi

# Get RequestUUID from the APP LOG
# Uncomment for debugging
# cat "$NOTARIZE_APP_LOG"

if ! grep -q "No errors uploading" "$NOTARIZE_APP_LOG"; then
    echo ">>>>>> Failed Uploading Package <<<<<<"
    exit 1
fi
RequestUUID=$(awk -F ' = ' '/RequestUUID/ {print $2}' "$NOTARIZE_APP_LOG")

echo "**** Checking Notarization Status (every 30 seconds)"
echo -n "**** "
# Check status every 30 seconds
while sleep 30; do
    echo -n "."

    # check notarization status
    if ! xcrun altool --notarization-info "$RequestUUID" \
                      --username "$APPLE_ACCT" \
                      --password "$APP_SPEC_PWD" > "$NOTARIZE_INFO_LOG" 2>&1; then
        cat "$NOTARIZE_INFO_LOG" 1>&2
        exit 1
    fi

    # Look for Status in the INFO LOG
    # Uncomment for debugging
    # cat "$NOTARIZE_INFO_LOG"

    # Continue checking until Status is no longer "in progress"
    if ! grep -q "Status: in progress" "$NOTARIZE_INFO_LOG"; then
        echo ""
        break
    fi

done

# Make sure the result is "success", then staple
if ! grep -q "Status: success" "$NOTARIZE_INFO_LOG"; then
    echo "**** There was a problem notarizing the package"
    echo "**** View the log for details:"
    awk -F ': ' '/LogFileURL/ {print $2}' "$NOTARIZE_INFO_LOG"
    exit 1
fi

echo "**** Stapling Notarization to the Package"
if ! xcrun stapler staple "$PACKAGE" > "$NOTARIZE_INFO_LOG"; then
    cat "$NOTARIZE_INFO_LOG" 1>&2
    exit 1
fi

echo "Notarize Salt Package Completed Successfully"
echo "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^"
