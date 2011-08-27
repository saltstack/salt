'''
Publish a command from a minion to a target
'''
# Import salt libs
import salt.crypt
# Import ZeroMQ
import zmq

def _get_socket():
    '''
    Return the ZeroMQ socket to use
    '''
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    return socket


def publish(tgt, fun, arg, expr_form='glob', returner=''):
    '''
    Publish a command from the minion out to other minions, publications need
    to be enabled on the Salt master and the minion needs to have permission
    to publish the command. The Salt master will also prevent a recursive
    publication loop, this means that a minion cannot command another minion
    to command another minion as that would create an infinate command loop.

    The arguments sent to the minion publish function are seperated with
    commas. This means that a minion who is executing a command with multiple
    args it will look like this:

    salt system.example.com publish.publish '*' user.add 'foo,1020,1020'

    CLI Example:
    salt system.example.com publish.publish '*' cmd.run 'ls -la /tmp'
    '''
    if fun == 'publish.publish':
        # Need to log something here
        return {}
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    payload = {'enc': 'aes'}
    load = {
            'cmd': 'minion_publish',
            'fun': fun,
            'arg': arg.split(','),
            'tgt': tgt,
            'ret': returner,
            'tok': tok,
            'id': __opts__['id']}
    payload['load'] = auth.crypticle.dumps(load)
    socket = _get_socket()
    socket.send_pyobj(payload)
    return auth.crypticle.loads(socket.recv_pyobj())
