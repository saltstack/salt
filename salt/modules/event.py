# -*- coding: utf-8 -*-
'''
Use the :doc:`Salt Event System </topics/event/index>` to fire events from the
master to the minion and vice-versa.
'''
# Import Python libs
import os

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
    if __opts__['transport'] == 'raet':
        sreq = salt.transport.Channel.factory(__opts__)
        load = {'id': __opts__['id'],
                'tag': tag,
                'data': data,
                'cmd': '_minion_event'}
        try:
            sreq.send(load)
        except Exception:
            pass
        return True

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
            return salt.utils.event.MinionEvent(__opts__).fire_event(
                {'data': data, 'tag': tag, 'events': None, 'pretag': None}, 'fire_master')
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
        event = salt.utils.event.get_event(
                __opts__['id'],
                sock_dir=__opts__['sock_dir'],
                opts=__opts__,
                transport=__opts__['transport'],
                listen=False)
        return event.fire_event(data, tag)
    except Exception:
        return False


def fire_master_env(tag, data=None, preload=None):
    '''
    Wraps :py:func:`fire_master` but the default event data is taken from the
    shell environment

    The ``data`` argument is optional. Environment variables can be overridden
    on an individual basis.

    This is a shorthand for firing an event using ``salt-call`` via an
    application that uses environment variables to expose data.

    For example, the popular Jenkins CI tool can send notifications to Salt of
    successful or failed builds or tests for additional action, such as
    deploying the new build. Add an "Execute shell" action to a Jenkins job
    with the example below. This avoids having to manually specify each and
    every environment variable as event data arguments.

    CLI Example:

    .. code-block:: bash

        salt-call event.fire_master_env myco/jenkins/build/success

    '''
    env_dict = {}
    env_dict.update(os.environ)

    if data:
        env_dict.update(data)

    return fire_master(env_dict, tag, preload=preload)
