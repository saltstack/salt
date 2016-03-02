#!/bin/sh
#
# Salt master
###################################

# LSB header

### BEGIN INIT INFO
# Provides:          salt-master
# Required-Start:    $all
# Required-Stop:
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Salt master control daemon
# Description:       This is a daemon that controls the Salt minions.
### END INIT INFO


# chkconfig header

# chkconfig: 345 96 05
# description:  This is a daemon that controls the Salt minions
#
# processname: /usr/bin/salt-master


DEBIAN_VERSION=/etc/debian_version
SUSE_RELEASE=/etc/SuSE-release
# Source function library.
if [ -f $DEBIAN_VERSION ]; then
   break
elif [ -f $SUSE_RELEASE -a -r /etc/rc.status ]; then
    . /etc/rc.status
else
    . /etc/rc.d/init.d/functions
fi

# Default values (can be overridden below)
SALTMASTER=/usr/bin/salt-master
PYTHON=/usr/bin/python
MASTER_ARGS=""

if [ -f /etc/default/salt ]; then
    . /etc/default/salt
fi

SERVICE=salt-master
PROCESS=salt-master

RETVAL=0

start() {
    echo -n $"Starting salt-master daemon: "
    if [ -f $SUSE_RELEASE ]; then
        startproc -f -p /var/run/$SERVICE.pid $SALTMASTER -d $MASTER_ARGS
        rc_status -v
    elif [ -e $DEBIAN_VERSION ]; then
        if [ -f $LOCKFILE ]; then
            echo -n "already started, lock file found"
            RETVAL=1
        elif $PYTHON $SALTMASTER -d $MASTER_ARGS >& /dev/null; then
            echo -n "OK"
            RETVAL=0
        fi
    else
        daemon --check $SERVICE $SALTMASTER -d $MASTER_ARGS
        RETVAL=$?
        [ $RETVAL -eq 0 ] && touch /var/lock/subsys/$SERVICE
        echo
        return $RETVAL
    fi
    RETVAL=$?
    echo
    return $RETVAL
}

stop() {
    echo -n $"Stopping salt-master daemon: "
    if [ -f $SUSE_RELEASE ]; then
        killproc -TERM $SALTMASTER
        rc_status -v
    elif [ -f $DEBIAN_VERSION ]; then
        # Added this since Debian's start-stop-daemon doesn't support spawned processes
        if ps -ef | grep "$PYTHON $SALTMASTER" | grep -v grep | awk '{print $2}' | xargs kill &> /dev/null; then
            echo -n "OK"
            RETVAL=0
        else
            echo -n "Daemon is not started"
            RETVAL=1
        fi
    else
        killproc $PROCESS
        RETVAL=$?
        echo
        [ $RETVAL -eq 0 ] && rm -f /var/lock/subsys/$SERVICE
        return $RETVAL
    fi
    RETVAL=$?
    echo
}

restart() {
   stop
   start
}

# See how we were called.
case "$1" in
    start|stop|restart)
        $1
        ;;
    status)
        if [ -f $SUSE_RELEASE ]; then
            echo -n "Checking for service salt-master "
            checkproc $SALTMASTER
            rc_status -v
        elif [ -f $DEBIAN_VERSION ]; then
            if [ -f $LOCKFILE ]; then
                RETVAL=0
                echo "salt-master is running."
            else
                RETVAL=1
                echo "salt-master is stopped."
            fi
        else
            status $PROCESS
            RETVAL=$?
        fi
        ;;
    condrestart)
        [ -f $LOCKFILE ] && restart || :
        ;;
    reload)
        echo "can't reload configuration, you have to restart it"
        RETVAL=1
        ;;
    *)
        echo $"Usage: $0 {start|stop|status|restart|condrestart|reload}"
        exit 1
        ;;
esac
exit $RETVAL
