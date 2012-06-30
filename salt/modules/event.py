'''
Fire events on the minion, events can be fired up to the master
'''
# Import Salt libs
import salt.crypt
import salt.payload

# Import third party libs
import zmq

def fire_master(data, tag):
    '''
    Fire an event off on the master server
    '''
    serial = salt.payload.Serial(__opts__)
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(__opts__['master_uri'])
    load = {'id': __opts__['id'],
            'tag': tag,
            'data': data,
            'cmd': '_minion_event'}
    auth = salt.crypt.SAuth(__opts__)
    payload = {'enc': 'aes'}
    payload['load'] = auth.crypticle.dumps(load)
    auth = salt.crypt.SAuth(__opts__)
    socket.send(serial.dumps(payload))
    socket.recv()
    return True
