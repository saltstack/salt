# -*- coding: utf-8 -*-
'''
Send events through Salt's event system during state runs
'''
from __future__ import absolute_import

# import salt libs
import salt.utils


def send(name,
        data=None,
        preload=None,
        with_env=False,
        with_grains=False,
        with_pillar=False,
        **kwargs):
    '''
    Send an event to the Salt Master

    .. versionadded:: 2014.7.0

    Accepts the same arguments as the :py:func:`event.send
    <salt.modules.event.send>` execution module of the same name.

    Example:

    .. code-block:: yaml

        # ...snip bunch of states above

        mycompany/mystaterun/status/update:
          event.send:
            - data:
                status: "Half-way through the state run!"

        # ...snip bunch of states below
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}
    ret['changes'] = {'tag': name, 'data': data}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Event would have been fired'
        return ret

    ret['result'] = __salt__['event.send'](name,
            data=data,
            preload=preload,
            with_env=with_env,
            with_grains=with_grains,
            with_pillar=with_pillar,
            **kwargs)
    ret['comment'] = 'Event fired'

    return ret


def wait(name, sfun=None):
    '''
    Fire an event on the Salt master event bus if called from a watch statement

    .. versionadded:: 2014.7.0

    Example:

    .. code-block:: yaml

        # Stand up a new web server.
        apache:
          pkg:
            - installed
            - name: httpd
          service:
            - running
            - enable: True
            - name: httpd

        # Notify the load balancer to update the pool once Apache is running.
        refresh_pool:
          event:
            - wait
            - name: mycompany/loadbalancer/pool/update
            - data:
                new_web_server_ip: {{ grains['ipv4'] | first() }}
            - watch:
              - pkg: apache
    '''
    # Noop. The state system will call the mod_watch function instead.
    return {'name': name, 'changes': {}, 'result': True, 'comment': ''}


mod_watch = salt.utils.alias_function(send, 'mod_watch')
fire_master = salt.utils.alias_function(send, 'fire_master')
