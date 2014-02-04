# -*- coding: utf-8 -*-
'''
Use the :doc:`Salt Event System </topics/event/index>` to fire events from the
master to the minion and vice-versa.
'''

# Import salt libs
import salt.crypt
import salt.utils.event
import salt.payload
import salt.transport

__proxyenabled__ = ['*']


def fire_master(data, tag, preload=None):
    '''
    Fire an event off up to the master server

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire_master '{"data":"my event data"}' 'tag'
    '''

    if preload:
        # If preload is specified, we must send a raw event (this is
        # slower because it has to independently authenticate)
        load = preload
        auth = salt.crypt.SAuth(__opts__)
        load.update({'id': __opts__['id'],
                'tag': tag,
                'data': data,
                'tok': auth.gen_token('salt'),
                'cmd': '_minion_event'})

        sreq = salt.transport.Channel.factory(__opts__)
        try:
            sreq.send(load)
        except Exception:
            pass
        return True
    else:
        # Usually, we can send the event via the minion, which is faster
        # because it is already authenticated
        try:
            return salt.utils.event.MinionEvent(**__opts__).fire_event(
                {'data': data, 'tag': tag, 'events': None, 'pretag': None}, "fire_master")
        except Exception:
            return False


def fire(data, tag):
    '''
    Fire an event on the local minion event bus. Data must be formed as a dict.

    CLI Example:

    .. code-block:: bash

        salt '*' event.fire '{"data":"my event data"}' 'tag'
    '''
    try:
        return salt.utils.event.MinionEvent(**__opts__).fire_event(data, tag)
    except Exception:
        return False
