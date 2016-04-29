# -*- coding: utf-8 -*-
'''
State module for Cisco NSO Proxy minions

.. versionadded: Carbon

For documentation on setting up the cisconso proxy minion look in the documentation
for :doc:`salt.proxy.cisconso</ref/proxy/all/salt.proxy.cisconso>`.
'''


def __virtual__():
    return 'cisconso.set_data_value' in __salt__


def value_present(name, datastore, path, config):
    '''
    Ensure a specific value exists at a given path

    :param name: The name for this rule
    :type  name: ``str``

    :param datastore: The datastore, e.g. running, operational.
        One of the NETCONF store IETF types
    :type  datastore: :class:`DatastoreType` (``str`` enum).

    :param path: The device path to set the value at,
        a list of element names in order, / seperated
    :type  path: ``list``, ``str`` OR ``tuple``

    :param config: The new value at the given path
    :type  config: ``dict``

    Examples:

    .. code-block:: yaml

        enable pap auth:
          cisconso.config_present:
            - name: enable_pap_auth
            - datastore: running
            - path: devices/device/ex0/config/sys/interfaces/serial/ppp0/authentication
            - config:
                authentication:
                    method: pap
                    "list-name": foobar

    '''
    ret = {'name': name,
           'result': False,
           'changes': {},
           'comment': ''}

    existing = __salt__['cisconso.get_data'](datastore, path)

    if cmp(existing, config):
        ret['result'] = True
        ret['comment'] = 'Config is already set'

    elif __opts__['test'] is True:
        ret['result'] = None
        ret['comment'] = 'Config will be added'
        ret['changes']['new'] = name

    else:
        __salt__['cisconso.set_data_value'](datastore, path, config)
        ret['result'] = True
        ret['comment'] = 'Successfully added config'
        ret['changes']['new'] = name

    return ret
