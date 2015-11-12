# -*- coding: utf-8 -*-
'''
Publish a command from a minion to a target
'''
from __future__ import absolute_import

# Import python libs
import time
import logging

# Import salt libs
import salt.crypt
import salt.payload
import salt.transport
import salt.utils.args
from salt.exceptions import SaltReqTimeoutError

log = logging.getLogger(__name__)

__virtualname__ = 'publish'


def __virtual__():
    return __virtualname__ if __opts__.get('transport', '') in ('zeromq', 'tcp') else False


def _parse_args(arg):
    '''
    yamlify `arg` and ensure it's outermost datatype is a list
    '''
    yaml_args = salt.utils.args.yamlify_arg(arg)

    if yaml_args is None:
        return []
    elif not isinstance(yaml_args, list):
        return [yaml_args]
    else:
        return yaml_args


def _publish(
        tgt,
        fun,
        arg=None,
        expr_form='glob',
        returner='',
        timeout=5,
        form='clean',
        wait=False):
    '''
    Publish a command from the minion out to other minions, publications need
    to be enabled on the Salt master and the minion needs to have permission
    to publish the command. The Salt master will also prevent a recursive
    publication loop, this means that a minion cannot command another minion
    to command another minion as that would create an infinite command loop.

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this::

        salt system.example.com publish.publish '*' user.add 'foo,1020,1020'

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    '''
    if 'master_uri' not in __opts__:
        log.error('Cannot run publish commands without a connection to a salt master. No command sent.')
        return {}
    if fun.startswith('publish.'):
        log.info('Cannot publish publish calls. Returning {}')
        return {}

    arg = _parse_args(arg)

    log.info('Publishing {0!r} to {master_uri}'.format(fun, **__opts__))
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'minion_pub',
            'fun': fun,
            'arg': arg,
            'tgt': tgt,
            'tgt_type': expr_form,
            'ret': returner,
            'tok': tok,
            'tmo': timeout,
            'form': form,
            'id': __opts__['id']}

    channel = salt.transport.Channel.factory(__opts__)
    try:
        peer_data = channel.send(load)
    except SaltReqTimeoutError:
        return '{0!r} publish timed out'.format(fun)
    if not peer_data:
        return {}
    # CLI args are passed as strings, re-cast to keep time.sleep happy
    if wait:
        loop_interval = 0.3
        matched_minions = set(peer_data['minions'])
        returned_minions = set()
        loop_counter = 0
        while len(returned_minions ^ matched_minions) > 0:
            load = {'cmd': 'pub_ret',
                    'id': __opts__['id'],
                    'tok': tok,
                    'jid': peer_data['jid']}
            ret = channel.send(load)
            returned_minions = set(ret.keys())

            end_loop = False
            if returned_minions >= matched_minions:
                end_loop = True
            elif (loop_interval * loop_counter) > timeout:
                # This may be unnecessary, but I am paranoid
                if len(returned_minions) < 1:
                    return {}
                end_loop = True

            if end_loop:
                if form == 'clean':
                    cret = {}
                    for host in ret:
                        cret[host] = ret[host]['ret']
                    return cret
                else:
                    return ret
            loop_counter = loop_counter + 1
            time.sleep(loop_interval)
    else:
        time.sleep(float(timeout))
        load = {'cmd': 'pub_ret',
                'id': __opts__['id'],
                'tok': tok,
                'jid': peer_data['jid']}
        ret = channel.send(load)
        if form == 'clean':
            cret = {}
            for host in ret:
                cret[host] = ret[host]['ret']
            return cret
        else:
            return ret


def publish(tgt, fun, arg=None, expr_form='glob', returner='', timeout=5):
    '''
    Publish a command from the minion out to other minions.

    Publications need to be enabled on the Salt master and the minion
    needs to have permission to publish the command. The Salt master
    will also prevent a recursive publication loop, this means that a
    minion cannot command another minion to command another minion as
    that would create an infinite command loop.

    The expr_form argument is used to pass a target other than a glob into
    the execution, the available options are:

    - glob
    - pcre
    - grain
    - grain_pcre
    - pillar
    - pillar_pcre
    - ipcidr
    - range
    - compound

    Note that for pillar matches must be exact, both in the pillar matcher
    and the compound matcher. No globbing is supported.

    The arguments sent to the minion publish function are separated with
    commas. This means that for a minion executing a command with multiple
    args it will look like this:

    .. code-block:: bash

        salt system.example.com publish.publish '*' user.add 'foo,1020,1020'
        salt system.example.com publish.publish 'os:Fedora' network.interfaces '' grain

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'


    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt '*' publish.publish test.kwarg arg='cheese=spam'

        Multiple keyword arguments should be passed as a list.

        .. code-block:: bash

            salt '*' publish.publish test.kwarg arg="['cheese=spam','spam=cheese']"



    '''
    return _publish(tgt,
                    fun,
                    arg=arg,
                    expr_form=expr_form,
                    returner=returner,
                    timeout=timeout,
                    form='clean',
                    wait=True)


def full_data(tgt, fun, arg=None, expr_form='glob', returner='', timeout=5):
    '''
    Return the full data about the publication, this is invoked in the same
    way as the publish function

    CLI Example:

    .. code-block:: bash

        salt system.example.com publish.full_data '*' cmd.run 'ls -la /tmp'

    .. admonition:: Attention

        If you need to pass a value to a function argument and that value
        contains an equal sign, you **must** include the argument name.
        For example:

        .. code-block:: bash

            salt '*' publish.full_data test.kwarg arg='cheese=spam'

    '''
    return _publish(tgt,
                    fun,
                    arg=arg,
                    expr_form=expr_form,
                    returner=returner,
                    timeout=timeout,
                    form='full',
                    wait=True)


def runner(fun, arg=None, timeout=5):
    '''
    Execute a runner on the master and return the data from the runner
    function

    CLI Example:

    .. code-block:: bash

        salt publish.runner manage.down
    '''
    arg = _parse_args(arg)

    if 'master_uri' not in __opts__:
        return 'No access to master. If using salt-call with --local, please remove.'
    log.info('Publishing runner {0!r} to {master_uri}'.format(fun, **__opts__))
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'minion_runner',
            'fun': fun,
            'arg': arg,
            'tok': tok,
            'tmo': timeout,
            'id': __opts__['id']}

    channel = salt.transport.Channel.factory(__opts__)
    try:
        return channel.send(load)
    except SaltReqTimeoutError:
        return '{0!r} runner publish timed out'.format(fun)
