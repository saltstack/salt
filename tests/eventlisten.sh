#!/bin/sh
#
# The following example monitors Salt's event bus in a background process
# watching for returns for a given job. Requires a POSIX environment and jq
# <http://stedolan.github.io/jq/>.
#
# Usage: ./eventlisten.sh '*' test.sleep 10

# Mimic fnmatch from the Python stdlib.
fnmatch() { case "$2" in $1) return 0 ;; *) return 1 ;; esac ; }
count() { printf '%s\n' "$#" ; }

listen() {
    events='events'
    mkfifo $events
    exec 3<>$events     # Hold the fd open.

    # Start listening to events before starting the command to avoid race
    # conditions.
    salt-run state.event count=-1 >&3 &
    events_pid=$!

    (
        timeout=$(( 60 * 60 ))
        sleep $timeout
        kill -s USR2 $$
    ) &
    timeout_pid=$!

    # Give the runner a few to connect to the event bus.
    printf 'Subscribing to the Salt event bus...\n'
    sleep 4

    trap '
        excode=$?; trap - EXIT;
        exec 3>&-
        kill '"${timeout_pid}"'
        kill '"${events_pid}"'
        rm '"${events}"'
        exit
        echo $excode
    ' INT TERM EXIT

    trap '
        printf '\''Timeout reached; exiting.\n'\''
        exit 4
    ' USR2

    # Run the command and get the JID.
    jid=$(salt --async "$@")
    jid="${jid#*: }"    # Remove leading text up to the colon.

    # Create the event tags to listen for.
    start_tag="salt/job/${jid}/new"
    ret_tag="salt/job/${jid}/ret/*"

    # ``read`` will block when no events are going through the bus.
    printf 'Waiting for tag %s\n' "$ret_tag"
    while read -r tag data; do
        if fnmatch "$start_tag" "$tag"; then
            minions=$(printf '%s\n' "${data}" | jq -r '.["minions"][]')
            num_minions=$(count $minions)
            printf 'Waiting for %s minions.\n' "$num_minions"
            continue
        fi

        if fnmatch "$ret_tag" "$tag"; then
            mid="${tag##*/}"
            printf 'Got return for %s.\n' "$mid"
            printf 'Pretty-printing event: %s\n' "$tag"
            printf '%s\n' "$data" | jq .

            minions="$(printf '%s\n' "$minions" | sed -e '/'"$mid"'/d')"
            num_minions=$(count $minions)
            if [ $((num_minions)) -eq 0 ]; then
                printf 'All minions returned.\n'
                break
            else
                printf 'Remaining minions: %s\n' "$num_minions"
            fi
        else
            printf 'Skipping tag: %s\n' "$tag"
            continue
        fi
    done <&3
}

listen "$@"
