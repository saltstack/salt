# -*- coding: utf-8 -*-
'''
Publish a command from a minion to a target
'''
from __future__ import absolute_import

# Import python libs
import time
import logging

# Import salt libs
import salt.payload
import salt.transport
import salt.utils.args
from salt.exceptions import SaltReqTimeoutError

log = logging.getLogger(__name__)

__virtualname__ = 'publish'


def __virtual__():
    return __virtualname__ if __opts__.get('transport', '') == 'raet' else False


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
        form='clean'):
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
    if fun == 'publish.publish':
        log.info('Function name is \'publish.publish\'. Returning {}')
        return {}

    arg = _parse_args(arg)

    load = {'cmd': 'minion_pub',
            'fun': fun,
            'arg': arg,
            'tgt': tgt,
            'tgt_type': expr_form,
            'ret': returner,
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
    time.sleep(float(timeout))
    load = {'cmd': 'pub_ret',
            'id': __opts__['id'],
            'jid': str(peer_data['jid'])}
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


    '''
    return _publish(tgt,
                    fun,
                    arg=arg,
                    expr_form=expr_form,
                    returner=returner,
                    timeout=timeout,
                    form='clean')


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
                    form='full')


def runner(fun, arg=None, timeout=5):
    '''
    Execute a runner on the master and return the data from the runner
    function

    CLI Example:

    .. code-block:: bash

        salt publish.runner manage.down
    '''
    arg = _parse_args(arg)

    load = {'cmd': 'minion_runner',
            'fun': fun,
            'arg': arg,
            'tmo': timeout,
            'id': __opts__['id']}

    channel = salt.transport.Channel.factory(__opts__)
    try:
        return channel.send(load)
    except SaltReqTimeoutError:
        return '{0!r} runner publish timed out'.format(fun)
