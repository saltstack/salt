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
    load = {'id': __opts__['id'],
            'tag': tag,
            'data': data,
            'cmd': '_minion_event'}
    auth = salt.crypt.SAuth(__opts__)
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    try:
        sreq.send('aes', auth.crypticle.dumps(load))
    except:
        pass
    return True
