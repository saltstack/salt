# -*- coding: utf-8 -*-
'''
Execute overstate functions
'''
# Import pytohn libs
from __future__ import print_function
from __future__ import absolute_import

import fnmatch
import json
import logging
import sys

# Import salt libs
import salt.overstate
import salt.syspaths
import salt.utils.event
from salt.exceptions import SaltInvocationError

LOGGER = logging.getLogger(__name__)


def over(saltenv='base', os_fn=None):
    '''
    .. versionadded:: 0.11.0

    .. warning::

        ``state.over`` is deprecated in favor of ``state.orchestrate``, and
        will be removed in the Salt feature release codenamed Boron.
        (Three feature releases after the 2014.7.0 release, which is codenamed
        Helium)

    Execute an overstate sequence to orchestrate the executing of states
    over a group of systems

    CLI Examples:

    .. code-block:: bash

        salt-run state.over base /path/to/myoverstate.sls
    '''
    salt.utils.warn_until(
            'Boron',
            'The state.over runner is on a deprecation path and will be '
            'removed in Salt Boron. Please migrate to state.orchestrate.'
            )

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
            __jid_event__.fire_event({'message': 'Stage execution results:'}, 'progress')
            for key, val in stage.items():
                if '_|-' in key:
                    __jid_event__.fire_event({'data': {'error': {key: val}}, 'outputter': 'highstate'}, 'progress')
                else:
                    __jid_event__.fire_event({'data': {key: val}, 'outputter': 'highstate'}, 'progress')
        elif isinstance(stage, list):
            # This is a stage
            if stage_num == 0:
                __jid_event__.fire_event({'message': 'Executing the following Over State:'}, 'progress')
            else:
                __jid_event__.fire_event({'message': 'Executed Stage:'}, 'progress')
            __jid_event__.fire_event({'data': stage, 'outputter': 'overstatestage'}, 'progress')
            stage_num += 1
    return overstate.over_run


def orchestrate(mods, saltenv='base', test=None, exclude=None, pillar=None):
    '''
    .. versionadded:: 0.17.0

    Execute a state run from the master, used as a powerful orchestration
    system.

    .. seealso:: More Orchestrate documentation

        * :ref:`Full Orchestrate Tutorial <orchestrate-runner>`
        * :py:mod:`Docs for the master-side state module <salt.states.saltmod>`

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
    ret = {minion.opts['id']: running, 'outputter': 'highstate'}
    return ret

# Aliases for orchestrate runner
orch = orchestrate  # pylint: disable=invalid-name
sls = orchestrate  # pylint: disable=invalid-name


def orchestrate_single(fun, name, test=None, queue=False, pillar=None, **kwargs):
    '''
    Execute a single state orchestration routine

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run state.orchestrate_single fun=salt.wheel name=key.list_all
    '''
    if pillar is not None and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary'
        )
    __opts__['file_client'] = 'local'
    minion = salt.minion.MasterMinion(__opts__)
    running = minion.functions['state.single'](
            fun,
            name,
            test=None,
            queue=False,
            pillar=pillar,
            **kwargs)
    ret = {minion.opts['id']: running}
    __jid_event__.fire_event({'data': ret, 'outputter': 'highstate'}, 'progress')
    return ret


def orchestrate_high(data, test=None, queue=False, pillar=None, **kwargs):
    '''
    Execute a single state orchestration routine

    .. versionadded:: 2015.5.0

    CLI Example:

    .. code-block:: bash

        salt-run state.orchestrate_high '{
            stage_one:
                {salt.state: [{tgt: "db*"}, {sls: postgres_setup}]},
            stage_two:
                {salt.state: [{tgt: "web*"}, {sls: apache_setup}, {
                    require: [{salt: stage_one}],
                }]},
            }'
    '''
    if pillar is not None and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary'
        )
    __opts__['file_client'] = 'local'
    minion = salt.minion.MasterMinion(__opts__)
    running = minion.functions['state.high'](
            data,
            test=None,
            queue=False,
            pillar=pillar,
            **kwargs)
    ret = {minion.opts['id']: running}
    __jid_event__.fire_event({'data': ret, 'outputter': 'highstate'}, 'progress')
    return ret


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
    __jid_event__.fire_event({'data': overstate.over, 'outputter': 'overstatestage'}, 'progress')
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

    .. seealso::

        See :glob:`tests/eventlisten.sh` for an example of usage within a shell
        script.
    '''
    sevent = salt.utils.event.get_event(
            'master',
            sock_dir or __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__)

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
            LOGGER.debug('Remaining event matches: {0}'.format(count))

            if count == 0:
                break
        else:
            LOGGER.debug('Skipping event tag: {0}'.format(ret['tag']))
            continue
