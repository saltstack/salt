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
#              This script will upload a copy of the package to Apple and wait
#              for the notarization to return. This can take several minutes.
#
#              If this command is run with sudo, you need to pass the `-E`
#              option to make sure the environment variables pass through to the
#              sudo environment. For example:
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
#         The following will notarize the 'salt-3006.1-1-signed.pkg' file
#
#         ./notarize.sh salt-3006.1-1-signed.pkg
#
# Environment Setup:
#
#     Define Environment Variables:
#         Create two environment variables for the Apple account and the
#         app-specific password associated with that account. To generate the
#         app-specific password see: https://support.apple.com/en-us/HT204397
#
#         export APPLE_ACCT="username@domain.com"
#         export APP_SPEC_PWD="abcd-efgh-ijkl-mnop"
#
################################################################################

#-------------------------------------------------------------------------------
# Variables
#-------------------------------------------------------------------------------
if [ "$1" == "" ]; then
    echo "Must supply a package to notarize"
    exit 1
else
    PACKAGE=$1
fi

BUNDLE_ID="com.saltstack.salt"
CMD_OUTPUT=$(mktemp -t cmd.log)

#-------------------------------------------------------------------------------
# Functions
#-------------------------------------------------------------------------------
# _usage
#
#   Prints out help text
_usage() {
     echo ""
     echo "Script to notarize the Salt package:"
     echo ""
     echo "usage: ${0}"
     echo "             [-h|--help]"
     echo ""
     echo "  -h, --help      this message"
     echo ""
     echo "  To notarize the Salt package:"
     echo "      example: $0 salt-3006.1-1-signed.pkg"
}

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
    cat "$CMD_OUTPUT" 1>&2
    echo "<<<<<< output"
    exit 1
}

#-------------------------------------------------------------------------------
# Get Parameters
#-------------------------------------------------------------------------------
while true; do
    if [[ -z "$1" ]]; then break; fi
    case "$1" in
        -h | --help )
            _usage
            exit 0
            ;;
        -*)
            echo "Invalid Option: $1"
            echo ""
            _usage
            exit 1
            ;;
        * )
            shift
            ;;
    esac
done

#-------------------------------------------------------------------------------
# Delete temporary files on exit
#-------------------------------------------------------------------------------
function finish {
    rm "$CMD_OUTPUT"
}
trap finish EXIT

#-------------------------------------------------------------------------------
# Script Start
#-------------------------------------------------------------------------------
printf "=%.0s" {1..80}; printf "\n"
echo "Notarize Salt Package"
printf -- "-%.0s" {1..80}; printf "\n"

#-------------------------------------------------------------------------------
# Submit app for notarization
#-------------------------------------------------------------------------------
_msg "Submitting package for notarization"
if xcrun altool --notarize-app \
                --primary-bundle-id "$BUNDLE_ID" \
                --username "$APPLE_ACCT" \
                --password "$APP_SPEC_PWD" \
                -f "$PACKAGE" > "$CMD_OUTPUT" 2>&1; then
    _success
else
    _failure
fi

# Get RequestUUID from the CMD_OUTPUT
# Uncomment for debugging
# cat "$CMD_OUTPUT"

_msg "Verifying successful upload"
if grep -q "No errors uploading" "$CMD_OUTPUT"; then
    _success
else
    echo ">>>>>> Failed Uploading Package <<<<<<" > "$CMD_OUTPUT"
    _failure
fi
RequestUUID=$(awk -F ' = ' '/RequestUUID/ {print $2}' "$CMD_OUTPUT")

# Clear CMD_OUTPUT
echo "" > "$CMD_OUTPUT"

echo "- Checking Notarization Status (every 30 seconds):"
echo -n "  "
# Though it usually takes 5 minutes, notarization can take up to 30 minutes
# Check status every 30 seconds for 40 minutes
tries=0
while sleep 30; do
    ((tries++))
    echo -n "."

    # check notarization status
    if ! xcrun altool --notarization-info "$RequestUUID" \
                      --username "$APPLE_ACCT" \
                      --password "$APP_SPEC_PWD" > "$CMD_OUTPUT" 2>&1; then
        echo ""
        cat "$CMD_OUTPUT" 1>&2
        exit 1
    fi

    # Look for Status in the CMD_OUTPUT
    # Uncomment for debugging
    # cat "$CMD_OUTPUT"

    # Continue checking until Status is no longer "in progress"
    if ! grep -q "Status: in progress" "$CMD_OUTPUT"; then
        echo ""
        break
    fi

    if (( tries > 80 )); then
        echo ""
        echo "Failed after 40 minutes"
        echo "Log: $CMD_OUTPUT"
        cat "$CMD_OUTPUT" 1>&2
        exit 1
    fi

done

# Make sure the result is "success", then staple
if ! grep -q "Status: success" "$CMD_OUTPUT"; then
    echo "**** There was a problem notarizing the package"
    echo "**** View the log for details:"
    awk -F ': ' '/LogFileURL/ {print $2}' "$CMD_OUTPUT"
    exit 1
fi
echo "  Notarization Complete"

_msg "Stapling notarization to the package"
if xcrun stapler staple "$PACKAGE" > "$CMD_OUTPUT"; then
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
