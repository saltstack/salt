# -*- coding: utf-8 -*-
'''
Execute overstate functions
'''
# Import pytohn libs
from __future__ import print_function

import fnmatch
import json
import logging
import sys

# Import salt libs
import salt.output
import salt.overstate
import salt.syspaths
import salt.utils.event
from salt.exceptions import SaltInvocationError

logger = logging.getLogger(__name__)


def over(saltenv='base', os_fn=None):
    '''
    .. versionadded:: 0.11.0

    Execute an overstate sequence to orchestrate the executing of states
    over a group of systems

    CLI Examples:

    .. code-block:: bash

        salt-run state.over base /path/to/myoverstate.sls
    '''
    stage_num = 0
    try:
        overstate = salt.overstate.OverState(__opts__, saltenv, os_fn)
    except IOError as exc:
        raise SaltInvocationError(
            '{0}: {1!r}'.format(exc.strerror, exc.filename)
        )
    for stage in overstate.stages_iter():
        if isinstance(stage, dict):
            # This is highstate data
            print('Stage execution results:')
            for key, val in stage.items():
                if '_|-' in key:
                    salt.output.display_output(
                            {'error': {key: val}},
                            'highstate',
                            opts=__opts__)
                else:
                    salt.output.display_output(
                            {key: val},
                            'highstate',
                            opts=__opts__)
        elif isinstance(stage, list):
            # This is a stage
            if stage_num == 0:
                print('Executing the following Over State:')
            else:
                print('Executed Stage:')
            salt.output.display_output(stage, 'overstatestage', opts=__opts__)
            stage_num += 1
    return overstate.over_run


def orchestrate(mods, saltenv='base', test=None, exclude=None, pillar=None):
    '''
    .. versionadded:: 0.17.0

    Execute a state run from the master, used as a powerful orchestration
    system.

    CLI Examples:

    .. code-block:: bash

        salt-run state.orchestrate webserver
        salt-run state.orchestrate webserver saltenv=dev test=True

    .. versionchanged:: 2014.1.1

        Runner renamed from ``state.sls`` to ``state.orchestrate``

    .. versionchanged:: 2014.7.0

        Runner uses the pillar variable
    '''
    if pillar is not None and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary'
        )
    __opts__['file_client'] = 'local'
    minion = salt.minion.MasterMinion(__opts__)
    running = minion.functions['state.sls'](
            mods,
            saltenv,
            test,
            exclude,
            pillar=pillar)
    ret = {minion.opts['id']: running}
    salt.output.display_output(ret, 'highstate', opts=__opts__)
    return ret

# Aliases for orchestrate runner
orch = orchestrate
sls = orchestrate


def show_stages(saltenv='base', os_fn=None):
    '''
    .. versionadded:: 0.11.0

    Display the OverState's stage data

    CLI Examples:

    .. code-block:: bash

        salt-run state.show_stages
        salt-run state.show_stages saltenv=dev /root/overstate.sls
    '''
    overstate = salt.overstate.OverState(__opts__, saltenv, os_fn)
    salt.output.display_output(
            overstate.over,
            'overstatestage',
            opts=__opts__)
    return overstate.over


def event(tagmatch='*', count=-1, quiet=False, sock_dir=None, pretty=False):
    r'''
    Watch Salt's event bus and block until the given tag is matched

    .. versionadded:: 2014.7.0

    This is useful for utilizing Salt's event bus from shell scripts or for
    taking simple actions directly from the CLI.

    Enable debug logging to see ignored events.

    :param tagmatch: the event is written to stdout for each tag that matches
        this pattern; uses the same matching semantics as Salt's Reactor.
    :param count: this number is decremented for each event that matches the
        ``tagmatch`` parameter; pass ``-1`` to listen forever.
    :param quiet: do not print to stdout; just block
    :param sock_dir: path to the Salt master's event socket file.
    :param pretty: Output the JSON all on a single line if ``False`` (useful
        for shell tools); pretty-print the JSON output if ``True``.

    CLI Examples:

    .. code-block:: bash

        # Reboot a minion and run highstate when it comes back online
        salt 'jerry' system.reboot && \\
            salt-run state.event 'salt/minion/jerry/start' count=1 quiet=True && \\
            salt 'jerry' state.highstate

        # Reboot multiple minions and run highstate when all are back online
        salt -L 'kevin,stewart,dave' system.reboot && \\
            salt-run state.event 'salt/minion/*/start' count=3 quiet=True && \\
            salt -L 'kevin,stewart,dave' state.highstate

        # Watch the event bus forever in a shell while-loop.
        salt-run state.event | while read -r tag data; do
            echo $tag
            echo $data | jq -colour-output .
        done

    The following example monitors Salt's event bus in a background process
    watching for returns for a given job. Requires a POSIX environment and jq
    <http://stedolan.github.io/jq/>.

    .. code-block:: bash

        #!/bin/sh
        # Usage: ./eventlisten.sh '*' test.sleep 10

        # Mimic fnmatch from the Python stdlib.
        fnmatch () { case "$2" in $1) return 0 ;; *) return 1 ;; esac ; }

        listen() {
            events='events'
            mkfifo $events
            exec 3<>$events     # Hold the fd open.

            # Start listening to events before starting the command to avoid race
            # conditions.
            salt-run state.event count=-1 >&3 &
            events_pid=$!

            trap '
                excode=$?; trap - EXIT;
                exec 3>&-
                kill '"${events_pid}"'
                rm '"${events}"'
                exit
                echo $excode
            ' INT TERM EXIT

            # Run the command and get the JID.
            jid=$(salt --async "$@")
            jid="${jid#*: }"    # Remove leading text up to the colon.

            # Create the event tags to listen for.
            start_tag="salt/job/${jid}/new"
            ret_tag="salt/job/${jid}/ret/*"

            printf 'Waiting for tag %s\n' "$ret_tag"
            while read -r tag data; do
                if fnmatch "$start_tag" "$tag"; then
                    minions=$(printf '%s\n' "${data}" | jq -r '.["minions"][]')
                    printf 'Waiting for minions: %s\n' "${minions}" | xargs
                    continue
                fi

                if fnmatch "$ret_tag" "$tag"; then
                    mid="${tag##*/}"
                    printf 'Got return for %s.\n' "$mid"
                    printf 'Pretty-printing event: %s\n' "$tag"
                    printf '%s\n' "$data" | jq .

                    minions="$(printf '%s\n' "$minions" | sed -e '/'"$mid"'/d')"
                    if (( ${#minions} )); then
                        printf 'Remaining minions: %s\n' "$minions" | xargs
                    else
                        break
                    fi
                else
                    printf 'Skipping tag: %s\n' "$tag"
                    continue
                fi
            done <&3
        }

        listen "$@"
    '''
    sevent = salt.utils.event.get_event(
            'master',
            sock_dir or __opts__['sock_dir'],
            __opts__['transport'])

    while True:
        ret = sevent.get_event(full=True)
        if ret is None:
            continue

        if fnmatch.fnmatch(ret['tag'], tagmatch):
            if not quiet:
                print('{0}\t{1}'.format(
                    ret['tag'],
                    json.dumps(
                        ret['data'],
                        sort_keys=pretty,
                        indent=None if not pretty else 4)))
                sys.stdout.flush()

            count -= 1
            logger.debug('Remaining event matches: {0}'.format(count))

            if count == 0:
                break
        else:
            logger.debug('Skipping event tag: {0}'.format(ret['tag']))
            continue
