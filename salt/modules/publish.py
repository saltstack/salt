'''
Publish a command from a minion to a target
'''

import zmq
import ast

import salt.crypt
import salt.payload

def _get_socket():
    '''
    Return the ZeroMQ socket to use
    '''
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    return socket

def _publish(tgt, fun, arg=None, expr_form='glob', returner='', timeout=5, data='clean'):
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

    CLI Example::

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    '''
    serial = salt.payload.Serial(__opts__)
    if fun == 'publish.publish':
        # Need to log something here
        return {}

    if not arg:
        arg = []

    try:
        if isinstance(ast.literal_eval(arg), dict):
            arg = [arg,]
    except:
        if isinstance(arg, basestring):
            arg = arg.split(',')

    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    payload = {'enc': 'aes'}
    load = {
            'cmd': 'minion_publish',
            'fun': fun,
            'arg': arg,
            'tgt': tgt,
            'ret': returner,
            'tok': tok,
            'tmo': timeout,
            'form': data,
            'id': __opts__['id']}
    payload['load'] = auth.crypticle.dumps(load)
    socket = _get_socket()
    socket.send(serial.dumps(payload))
    return auth.crypticle.loads(serial.loads(socket.recv()))

def publish(tgt, fun, arg=None, expr_form='glob', returner='', timeout=5):
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

    CLI Example::

        salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    '''
    return _publish(tgt, fun, arg, expr_form, returner, timeout, 'clean')

def full_data(tgt, fun, arg=None, expr_form='glob', returner='', timeout=5):
    '''
    Return the full data about the publication, this is invoked in the same
    way as the publish function

    CLI Example::

        salt system.example.com publish.full_data '*' cmd.run 'ls -la /tmp'
    '''
    return _publish(tgt, fun, arg, expr_form, returner, timeout, 'full')
