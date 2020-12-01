#!/bin/bash
################################################################################
#
# Title: Notarize Package Script for macOS
# Authors: Shane Lee
# Date: December 2020
#
# Description: This notarizes the macOS Installer Package (.pkg)
#
# Requirements:
#     - Xcode Command Line Tools (xcode-select --install)
#
# Usage:
#     This script must be passed 2 parameters
#
#         $1 : <signed package>
#             The package that will be notarized (must be signed)
#
#         $2 : <notarized package>
#             The name to give the notarized package (can't be the same as the
#             signed package)
#
#     Example:
#         The following will notarize the 'salt-v2015.8.3-signed.pkg' file and
#         save it as 'salt-v2015.8.3-notarized.pkg'
#
#         ./notarized.sh salt-v2015.8.3-signed.pkg salt-v2015.8.3-notarized.pkg
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

################################################################################
# Check input parameters
################################################################################
if [ "$1" == "" ]; then
    echo "Must supply a package to notarize"
else
    SIGNED_PACKAGE=$1
fi

if [ "$2" == "" ]; then
    echo "Must supply a notarized package name"
else
    NOTARIZED_PACKAGE=$1
fi

################################################################################
# Environment Variables
################################################################################
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
if ! xcrun altool --notarize-app \
                  --primary-bundle-id "$BUNDLE_ID" \
                  --username "$APPLE_ACCT" \
                  --password "$APP_SPEC_PWD" \
                  -f "$SIGNED_PACKAGE" > "$NOTARIZE_APP_LOG" 2>&1; then
    cat "$NOTARIZE_APP_LOG" 1>&2
    exit 1
fi

# Get RequestUUID from the APP LOG
cat "$NOTARIZE_APP_LOG"
RequestUUID=$(awk -F ' = ' '/RequestUUID/ {print $2}' "$NOTARIZE_APP_LOG")

# Check status every 30 seconds
while sleep 30 && date; do
echo "Waiting for Apple to approve the notarization so it can be stapled.
      This can take a few minutes or more. Script auto checks every 30 sec"

	  # check notarization status
	  if ! xcrun altool --notarization-info "$RequestUUID" \
	                    --username "$APPLE_ACCT" \
	                    --password "$APP_SPEC_PWD" > "$NOTARIZE_INFO_LOG" 2>&1; then
		    cat "$NOTARIZE_INFO_LOG" 1>&2
		    exit 1
	  fi

	  # Look for Status in the INFO LOG
	  cat "$NOTARIZE_INFO_LOG"

	  # once notarization is complete, run stapler and exit
	  if ! grep -q "Status: in progress" "$NOTARIZE_INFO_LOG"; then
    		xcrun stapler staple "$NOTARIZED_PACKAGE"
    		exit $?
	  fi

done