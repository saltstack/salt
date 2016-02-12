# -*- coding: utf-8 -*-
'''
Use consul data as a Pillar source

:depends:  - python-consul

In order to use an consul server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_consul_config:
      consul.host: 127.0.0.1
      consul.port: 8500

After the profile is created, configure the external pillar system to use it.
Optionally, a root may be specified.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config

    ext_pillar:
      - consul: my_consul_config root=/salt

Using these configuration profiles, multiple consul sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config
      - consul: my_other_consul_config

Either the ``minion_id``, or the ``role`` grain  may be used in the ``root``
path to expose minion-specific information stored in consul.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config root=/salt/%(minion_id)s
      - consul: my_consul_config root=/salt/%(role)s

Minion-specific values may override shared values when the minion-specific root
appears after the shared root:

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config root=/salt-shared
      - consul: my_other_consul_config root=/salt-private/%(minion_id)s

If using the ``role`` grain in the consul key path, be sure to define it using
`/etc/salt/grains`, or similar:

.. code-block:: yaml

    role: my-minion-role

'''
from __future__ import absolute_import

# Import python libs
import logging

import re

from salt.exceptions import CommandExecutionError
from salt.utils.dictupdate import update as dict_merge

# Import third party libs
try:
    import consul
    HAS_CONSUL = True
except ImportError:
    HAS_CONSUL = False

__virtualname__ = 'consul'

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if python-consul is installed
    '''
    return __virtualname__ if HAS_CONSUL else False


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Check consul for all data
    '''
    comps = conf.split()

    profile = None
    if comps[0]:
        profile = comps[0]
    client = get_conn(__opts__, profile)

    path = ''
    if len(comps) > 1 and comps[1].startswith('root='):
        path = comps[1].replace('root=', '')

    role = __salt__['grains.get']('role')
    # put the minion's ID in the path if necessary
    path %= {
        'minion_id': minion_id,
        'role': role
    }

    try:
        pillar = fetch_tree(client, path)
    except KeyError:
        log.error('No such key in consul profile {0}: {1}'
                  .format(profile, path))
        pillar = {}

    return pillar


def consul_fetch(client, path):
    '''
    Query consul for all keys/values within base path
    '''
    return client.kv.get(path, recurse=True)


def fetch_tree(client, path):
    '''
    Grab data from consul, trim base path and remove any keys which
    are folders. Take the remaining data and send it to be formatted
    in such a way as to be used as pillar data.
    '''
    index, items = consul_fetch(client, path)
    ret = {}
    has_children = re.compile(r'/$')

    log.debug('Fetched items: %r', format(items))

    if items is None:
        return ret
    for item in reversed(items):
        key = re.sub(r'^' + path + '/?', '', item['Key'])
        if key != "":
            log.debug('key/path - {0}: {1}'.format(path, key))
            log.debug('has_children? %r', format(has_children.search(key)))
        if has_children.search(key) is None:
            ret = pillar_format(ret, key.split('/'), item['Value'])
            log.debug('Fetching subkeys for key: %r', format(item))

    return ret


def pillar_format(ret, keys, value):
    '''
    Perform data formatting to be used as pillar data and
    merge it with the current pillar data
    '''
    # drop leading/trailing whitespace, if any
    value = value.strip(' \t\n\r')
    # skip it
    if value is None:
        return ret
    # if wrapped in quotes, drop them
    if value[0] == value[-1] == '"':
        pillar_value = value[1:-1]
    # if we have a list, reformat into a list
    if value[0] == '-' and value[1] == ' ':
        array_data = value.split('\n')
        # drop the '- ' on each element
        pillar_value = [elem[2:] for elem in array_data]
    # leave it be
    else:
        pillar_value = value
    keyvalue = keys.pop()
    pil = {keyvalue: pillar_value}
    keys.reverse()
    for k in keys:
        pil = {k: pil}

    return dict_merge(ret, pil)


def get_conn(opts, profile):

    '''
    Return a client object for accessing consul
    '''
    opts_pillar = opts.get('pillar', {})
    opts_master = opts_pillar.get('master', {})

    opts_merged = {}
    opts_merged.update(opts_master)
    opts_merged.update(opts_pillar)
    opts_merged.update(opts)

    if profile:
        conf = opts_merged.get(profile, {})
    else:
        conf = opts_merged

    consul_host = conf.get('consul.host', '127.0.0.1')
    consul_port = conf.get('consul.port', 8500)

    if HAS_CONSUL:
        return consul.Consul(host=consul_host, port=consul_port)
    else:
        raise CommandExecutionError(
            '(unable to import consul, '
            'module most likely not installed. Download python-consul '
            'module and be sure to import consul)'
        )
