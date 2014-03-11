# -*- coding: utf-8 -*-
'''
Execute overstate functions
'''
# Import pytohn libs
from __future__ import print_function

import fnmatch
import json
import logging

# Import salt libs
import salt.overstate
import salt.output
import salt.syspaths
import salt.utils.event

logger = logging.getLogger(__name__)


def over(saltenv='base', os_fn=None):
    '''
    Execute an overstate sequence to orchestrate the executing of states
    over a group of systems

    CLI Examples:

    .. code-block:: bash

        salt-run state.over base /path/to/myoverstate.sls
    '''
    stage_num = 0
    overstate = salt.overstate.OverState(__opts__, saltenv, os_fn)
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


def sls(mods, saltenv='base', test=None, exclude=None, pillar=None):
    '''
    Execute a state run from the master, used as a powerful orchestration
    system.

    CLI Examples:

    .. code-block:: bash

        salt-run state.sls webserver
        salt-run state.sls webserver saltenv=dev test=True
    '''
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


def show_stages(saltenv='base', os_fn=None):
    '''
    Display the stage data to be executed

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


def event(tagmatch='*', count=1, quiet=False, sock_dir=None):
    '''
    Watch Salt's event bus and block until the given tag is matched

    This is useful for taking some simple action after an event is fired via
    the CLI without having to use Salt's Reactor.

    :param tagmatch: the event is written to stdout for each tag that matches
        this pattern; uses the same matching semantics as Salt's Reactor.
    :param count: this number is decremented for each event that matches the
        ``tagmatch`` parameter; pass ``-1`` to listen forever.
    :param quiet: do not print to stdout; just block
    :param sock_dir: path to the Salt master's event socket file.

    CLI Examples:

    .. code-block:: bash

        # Reboot a minion and run highstate when it comes back online
        salt 'jerry' system.reboot && \\
            salt-run state.event 'salt/minion/jerry/start' quiet=True && \\
            salt 'jerry' state.highstate

        # Reboot multiple minions and run highstate when all are back online
        salt -L 'kevin,stewart,dave' system.reboot && \\
            salt-run state.event 'salt/minion/*/start' count=3 quiet=True && \\
            salt -L 'kevin,stewart,dave' state.highstate

        # Watch the event bus forever in a shell for-loop;
        # note, slow-running tasks here will fill up the input buffer.
        salt-run state.event count=-1 | while read -r tag data; do
            echo $tag
            echo $data | jq -colour-output .
        done

        wait

    Enable debug logging to see ignored events.
    '''
    sevent = salt.utils.event.SaltEvent('master',
            sock_dir or __opts__['sock_dir'])

    while True:
        ret = sevent.get_event(full=True)
        if ret is None:
            continue

        if fnmatch.fnmatch(ret['tag'], tagmatch):
            if not quiet:
                print('{0}\t{1}'.format(ret['tag'], json.dumps(ret['data'])))

            count -= 1
            logger.debug('Remaining event matches: {0}'.format(count))

            if count == 0:
                break
        else:
            logger.debug('Skipping event tag: {0}'.format(ret['tag']))
            continue
