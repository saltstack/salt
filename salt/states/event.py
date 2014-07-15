# -*- coding: utf-8 -*-
'''
Send events through Salt's event system during state runs
'''


def fire_master(name, data):
    '''
    Fire an event on the Salt master event bus

    .. versionadded:: 2014.7.0

    name
        The tag for the event
    data
        The data sent through the event

    Example:

    .. code-block:: yaml

        # ...snip bunch of states above

        mycompany/mystaterun/status/update:
          event:
            - fire_master
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

    ret['result'] = __salt__['event.fire_master'](data, name)
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

mod_watch = fire_master
