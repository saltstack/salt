# -*- coding: utf-8 -*-
def fire_master(name, data):
    '''
    Fire an event on the Salt master event bus

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


def wait(name, sfun=None):
    '''
    Fire an event on the Salt master event bus if called from a watch statement
    and the watched state is successful and has changes

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
                ??? # Bad example here. What makes more sense?
            - watch:
              - service: apache
    '''


def mod_watch(name, sfun=None):
    '''
    Fire an event on the Salt master event bus if called from a watch statement

    Changes from the watched state can be included in the event.

    '''

# TODO: how to pull the watched state ID so we can look up the result of that
# state in the running dict.
#
# __running__ = {
#     'grains_|-add_role_|-roles_|-list_present': {
#         'comment': 'Append value web9 to grain roles',
#         '__run_num__': 0,
#         'changes': True,
#         'name': 'roles',
#         'result': True
#     }
# }
