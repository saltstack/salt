'''
Use the :doc:`Salt Event System </topics/event/index>` to fire events from the
master to the minion and vice-versa.
'''

# Import salt libs
import salt.crypt
import salt.utils.event
import salt.payload


def fire_master(data, tag):
    '''
    Fire an event off up to the master server

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire_master 'stuff to be in the event' 'tag'
    '''
    load = {'id': __opts__['id'],
            'tag': tag,
            'data': data,
            'cmd': '_minion_event'}
    auth = salt.crypt.SAuth(__opts__)
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    try:
        sreq.send('aes', auth.crypticle.dumps(load))
    except Exception:
        pass
    return True


def fire(data, tag):
    '''
    Fire an event on the local minion event bus

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire 'stuff to be in the event' 'tag'
    '''
    try:
        return salt.utils.event.MinionEvent(**__opts__).fire_event(data, tag)
    except Exception:
        return False
