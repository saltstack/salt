#!/bin/bash
############################################################################
# Commandline Help
############################################################################
display_help() {
    echo "################################################################"
    echo "Salt Minion Configuration Script"
    echo
    echo "Use this script to configure the minion id as well as the master"
    echo "the minion should connect to. The settings will be changed and"
    echo "the service will be restarted. Must be run as sudo"
    echo
    echo "This script accepts the following parameters:"
    echo
    echo "  -i, --minion-id    The ID to assign this minion"
    echo "  -m, --master       The hostname/IP address of the master"
    echo "  -h, --help         Display this help message"
    echo
    echo "Examples:"
    echo
    echo "  sudo salt-config -i mac_minion -m master.apple.com"
    echo
    echo "  sudo salt-config --minion-id mac_minion --master 10.10.1.10"
    echo
    echo "################################################################"
    exit 1
}

############################################################################
# Parameters
############################################################################
# Initialize Parameters
master=''
minion_id=''
changed=0
CONF_DIR="/etc/salt"

############################################################################
# Check for parameters
############################################################################
# Check for no parameters
if [ $# -eq 0 ] ; then
    echo "ERROR: No Parameters Passed"
    echo "       To see help use --help"
    exit 1
fi

# Check for valid parameters
while [ $# -gt 0 ]; do
    case "$1" in
        -i | --minion-id)
            minion_id="$2"
            shift 2
            ;;
        -m | --master)
            master="$2"
            shift 2
            ;;
        -h | --help) # Display Help
            display_help
            ;;
        *)
            break
    esac
done

# Check for additional parameters
if [ -n "$1" ] ; then
    echo "ERROR: Unknown Parameter Passed: $1"
    echo "       To see help use --help"
    exit 1
fi

############################################################################
# minion.d directory
############################################################################
if [ ! -d "$CONF_DIR/minion.d" ]; then
    mkdir "$CONF_DIR/minion.d"
fi

############################################################################
# Minion ID
############################################################################
if [ -n "$minion_id" ]; then
    echo "Changing minion ID: $minion_id"
    sed -i '' -e '/id:/ s/^#*/#/' $CONF_DIR/minion
    echo "id: $minion_id" > $CONF_DIR/minion.d/minion_id.conf
    changed=1
fi

############################################################################
# Master ID
############################################################################
if [ ! -z "$master" ]; then
    echo "Changing master: $master"
    sed -i '' -e '/master:/ s/^#*/#/' $CONF_DIR/minion
    echo "master: $master" > $CONF_DIR/minion.d/master_id.conf
    changed=1
fi

############################################################################
# Restart Minion
############################################################################
if (( changed == 1 )); then
    echo "Restarting the minion service..."
    launchctl kickstart -k system/com.saltstack.salt.minion
fi
exit 0
