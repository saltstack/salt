# -*- coding: utf-8 -*-
'''
Publish a command from a minion to a target
'''

# Import python libs
import time
import ast
import logging

# Import salt libs
import salt.crypt
import salt.payload
import salt.transport
from salt.exceptions import SaltReqTimeoutError
from salt._compat import string_types, integer_types

log = logging.getLogger(__name__)


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
        # Need to log something here
        return {}

    arg = _normalize_arg(arg)

    log.info('Publishing {0!r} to {master_uri}'.format(fun, **__opts__))
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
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

    sreq = salt.transport.Channel.factory(__opts__)
    try:
        peer_data = sreq.send(load)
        # peer_data = auth.crypticle.loads(
        #     sreq.send('aes', auth.crypticle.dumps(load), 1))
    except SaltReqTimeoutError:
        return '{0!r} publish timed out'.format(fun)
    if not peer_data:
        return {}
    # CLI args are passed as strings, re-cast to keep time.sleep happy
    time.sleep(float(timeout))
    load = {'cmd': 'pub_ret',
            'id': __opts__['id'],
            'tok': tok,
            'jid': peer_data['jid']}
    ret = sreq.send(load)
    #  auth.crypticle.loads(
    #         sreq.send('aes', auth.crypticle.dumps(load), 5))
    if form == 'clean':
        cret = {}
        for host in ret:
            cret[host] = ret[host]['ret']
        return cret
    else:
        return ret


def _normalize_arg(arg):
    '''
    Take the arguments and return them in a standard list
    '''
    if not arg:
        arg = []

    try:
        # Numeric checks here because of all numeric strings, like JIDs
        if isinstance(ast.literal_eval(arg), (dict, integer_types, long)):
            arg = [arg]
    except Exception:
        if isinstance(arg, string_types):
            arg = arg.split(',')

    return arg


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
    arg = _normalize_arg(arg)

    log.info('Publishing runner {0!r} to {master_uri}'.format(fun, **__opts__))
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'minion_runner',
            'fun': fun,
            'arg': arg,
            'tok': tok,
            'tmo': timeout,
            'id': __opts__['id']}

    sreq = salt.transport.Channel.factory(__opts__)
    try:
        return sreq.send(load)
        # return auth.crypticle.loads(
        #    sreq.send('aes', auth.crypticle.dumps(load), 1))
    except SaltReqTimeoutError:
        return '{0!r} runner publish timed out'.format(fun)
