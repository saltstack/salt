'''
Configuration management using Augeas
=====================================

:strong:`NOTE:` This state requires the Augeas Python adapter. See the
documentation for the :mod:`augeas_cfg <salt.modules.augeas_cfg>` module for
more information.

Augeas can be used to manage configuration files. Currently only the 'set'
command is supported through this state file. The Augeas module also has
support for get, match, remove, etc.

Examples:

Set the first entry in ``/etc/hosts`` to localhost:

.. code-block:: yaml
    hosts:
      augeas.setvalue:
        - changes:
          - /files/etc/hosts/1/canonical localhost

Add a new host to /etc/hosts with the ip address 192.168.1.1 and hostname test

.. code-block:: yaml
    hosts:
      augeas.setvalue:
        - changes:
          - /files/etc/hosts/01/ipaddr 192.168.1.1
          - /files/etc/hosts/01/canonical test

You can also set a prefix if you want to avoid redundancy:

.. code-block:: yaml

    nginx-conf:
      augeas.setvalue:
        - prefix: /files/etc/nginx/nginx.conf
        - changes:
          - user www-data
          - worker_processes 2
          - http/server_tokens off
          - http/keepalive_timeout 65

'''


def setvalue(name, prefix=None, changes=(), **kwargs):
    '''
    Set a value for a specific augeas path
    '''

    ret = {'name': name, 'result': None, 'comment': '', 'changes': {}}

    args = []
    for change in changes:
        tpl = change.split(None, 1)
        if len(tpl) != 2:
            raise ValueError('Change must have format "foo bar", was given {0}'
                             .format(change))

        args.append(str(tpl[0]))
        args.append(str(tpl[1]))

    if prefix is not None:
        args.insert(0, 'prefix=%s' % prefix)

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Calling setvalue with {0}'.format(args)
        return ret

    call = __salt__['augeas.setvalue'](*args)

    ret['result'] = call['retval']

    if ret['result'] is False:
        ret['comment'] = 'Error: %s' % call['error']
        return ret

    ret['comment'] = 'Success'
    ret['changes'] = '%s' % changes

    return ret
