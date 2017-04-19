# -*- coding: utf-8 -*-
'''
Execute orchestration functions
'''
# Import pytohn libs
from __future__ import absolute_import, print_function
import logging

# Import salt libs
import salt.loader
import salt.utils
import salt.utils.event
from salt.exceptions import SaltInvocationError

LOGGER = logging.getLogger(__name__)


def orchestrate(mods,
                saltenv='base',
                test=None,
                exclude=None,
                pillar=None,
                pillarenv=None,
                pillar_enc=None,
                orchestration_jid=None):
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
        salt-run state.orchestrate webserver saltenv=dev pillarenv=aws

    .. versionchanged:: 2014.1.1

        Runner renamed from ``state.sls`` to ``state.orchestrate``

    .. versionchanged:: 2014.7.0

        Runner uses the pillar variable

    .. versionchanged:: develop

        Runner uses the pillar_enc variable that allows renderers to render the pillar.
        This is usable when supplying the contents of a file as pillar, and the file contains
        gpg-encrypted entries.

    .. seealso:: GPG renderer documentation

    CLI Examples:

    .. code-block:: bash

       salt-run state.orchestrate webserver pillar_enc=gpg pillar="$(cat somefile.json)"

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
            pillar=pillar,
            pillarenv=pillarenv,
            pillar_enc=pillar_enc,
            orchestration_jid=orchestration_jid)
    ret = {'data': {minion.opts['id']: running}, 'outputter': 'highstate'}
    res = salt.utils.check_state_result(ret['data'])
    if res:
        ret['retcode'] = 0
    else:
        ret['retcode'] = 1
    return ret

# Aliases for orchestrate runner
orch = salt.utils.alias_function(orchestrate, 'orch')
sls = salt.utils.alias_function(orchestrate, 'sls')


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

def orchestrate_show_sls(mods,
                         saltenv='base',
                         test=None,
                         exclude=None,
                         pillar=None,
                         pillarenv=None,
                         pillar_enc=None):
    '''
    Display the state data from a specific sls, or list of sls files, after
    being render using the master minion.

    Note, the master minion adds a "_master" suffix to it's minion id.

    .. seealso:: The state.show_sls module function

    CLI Example:
    .. code-block:: bash

        salt-run state.orch_show_sls my-orch-formula.my-orch-state 'pillar={ nodegroup: ng1 }'
    '''
    if pillar is not None and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary')

    __opts__['file_client'] = 'local'
    minion = salt.minion.MasterMinion(__opts__)
    running = minion.functions['state.show_sls'](
        mods,
        saltenv,
        test,
        exclude,
        pillar=pillar,
        pillarenv=pillarenv,
        pillar_enc=pillar_enc)

    ret = {minion.opts['id']: running}
    return ret

orch_show_sls = salt.utils.alias_function(orchestrate_show_sls, 'orch_show_sls')

def event(tagmatch='*',
        count=-1,
        quiet=False,
        sock_dir=None,
        pretty=False,
        node='master'):
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
    :param node: Watch the minion-side or master-side event bus.
        .. versionadded:: 2016.3.0

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
            echo $data | jq --color-output .
        done

    .. seealso::

        See :blob:`tests/eventlisten.sh` for an example of usage within a shell
        script.
    '''
    statemod = salt.loader.raw_mod(__opts__, 'state', None)

    return statemod['state.event'](
            tagmatch=tagmatch,
            count=count,
            quiet=quiet,
            sock_dir=sock_dir,
            pretty=pretty,
            node=node)
