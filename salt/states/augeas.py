# -*- coding: utf-8 -*-
'''
Configuration management using Augeas
=====================================

:strong:`NOTE:` This state requires the ``augeas`` Python module.

.. _Augeas: http://augeas.net/

Augeas_ can be used to manage configuration files. Currently only the ``set``
command is supported via this state. The :mod:`augeas
<salt.modules.augeas_cfg>` module also has support for get, match, remove, etc.

Examples:

Set the first entry in ``/etc/hosts`` to ``localhost``:

.. code-block:: yaml

    hosts:
      augeas.setvalue:
        - changes:
          - /files/etc/hosts/1/canonical: localhost

Add a new host to ``/etc/hosts`` with the IP address ``192.168.1.1`` and
hostname ``test``:

.. code-block:: yaml

    hosts:
      augeas.setvalue:
        - changes:
          - /files/etc/hosts/2/ipaddr: 192.168.1.1
          - /files/etc/hosts/2/canonical: foo.bar.com
          - /files/etc/hosts/2/alias[1]: foosite
          - /files/etc/hosts/2/alias[2]: foo

You can also set a prefix if you want to avoid redundancy:

.. code-block:: yaml

    nginx-conf:
      augeas.setvalue:
        - prefix: /files/etc/nginx/nginx.conf
        - changes:
          - user: www-data
          - worker_processes: 2
          - http/server_tokens: off
          - http/keepalive_timeout: 65

'''


def __virtual__():
    return 'augeas' if 'augeas.setvalue' in __salt__ else False


def setvalue(name, prefix=None, changes=None, **kwargs):
    '''
    Set a value for a specific augeas path
    '''
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    args = []
    if not changes:
        ret['comment'] = '\'changes\' must be specified'
        return ret
    else:
        if not isinstance(changes, list):
            ret['comment'] = '\'changes\' must be formatted as a list'
            return ret
        for change in changes:
            if not isinstance(change, dict) or len(change) > 1:
                ret['comment'] = 'Invalidly-formatted change'
                return ret
            key = next(iter(change))
            args.extend([key, change[key]])

    if prefix is not None:
        args.insert(0, 'prefix={0}'.format(prefix))

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Calling setvalue with {0}'.format(args)
        return ret

    call = __salt__['augeas.setvalue'](*args)

    ret['result'] = call['retval']

    if ret['result'] is False:
        ret['comment'] = 'Error: {0}'.format(call['error'])
        return ret

    ret['comment'] = 'Success'
    for change in changes:
        ret['changes'].update(change)
    return ret
