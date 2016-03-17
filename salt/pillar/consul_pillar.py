# -*- coding: utf-8 -*-
'''
Use Consul K/V as a Pillar source with values parsed as YAML

:depends:  - python-consul

In order to use an consul server, a profile must be created in the master
configuration file:

.. code-block:: yaml

    my_consul_config:
      consul.host: 127.0.0.1
      consul.port: 8500
      consul.token: b6376760-a8bb-edd5-fcda-33bc13bfc556
      consul.scheme: http
      consul.consistency: default
      consul.dc: dev
      consul.verify: True

All parameters are optional.

If you have a multi-datacenter Consul cluster you can map your ``pillarenv``s
to your data centers by providing a dictionary of mappings in ``consul.dc``
field:

.. code-block:: yaml

    my_consul_config:
      consul.dc:
        dev: us-east-1
        prod: us-west-1

In the example above we specifying static mapping between Pillar environments
and data centers: the data for ``dev`` and ``prod`` Pillar environments will
be fetched from ``us-east-1`` and ``us-west-1`` datacenter respectively.

In fact when ``consul.dc`` is set to dictionary keys are processed as regular
expressions (that can capture named parameters) and values are processed as
string templates as per PEP 3101.

.. code-block:: yaml

    my_consul_config:
      consul.dc:
        ^dev-.*$: dev-datacenter
        ^(?P<region>.*)-prod$: prod-datacenter-{region}

This example maps all Pillar environments starting with ``dev-`` to
``dev-datacenter`` whereas Pillar environment like ``eu-prod`` will be
mapped to ``prod-datacenter-eu``.

Before evaluation patterns are sorted by length in descending order.

If Pillar environment names correspond to data center names a single pattern
can be used:

.. code-block:: yaml

    my_consul_config:
      consul.dc:
        ^(?P<env>.*)$: '{env}'

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

import yaml

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
    # if value is empty in Consul then it's None here - skip it
    if value is None:
        return ret

    # If value is not None then it's a string
    # Use YAML to parse the data
    # YAML strips whitespaces unless they're surrounded by quotes
    pillar_value = yaml.load(value)

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

    params = {}
    for key in ('host', 'port', 'token', 'scheme', 'consistency', 'dc', 'verify'):
        prefixed_key = 'consul.{key}'.format(key=key)
        if prefixed_key in conf:
            params[key] = conf[prefixed_key]

    if 'dc' in params:
        pillarenv = opts_merged.get('pillarenv') or 'base'
        params['dc'] = _resolve_datacenter(params['dc'], pillarenv)

    if HAS_CONSUL:
        return consul.Consul(**params)
    else:
        raise CommandExecutionError(
            '(unable to import consul, '
            'module most likely not installed. Download python-consul '
            'module and be sure to import consul)'
        )


def _resolve_datacenter(dc, pillarenv):
    '''
    If ``dc`` is a string - return it as is.

    If it's a dict then sort it in descending order by key length and try
    to use keys as RegEx patterns to match against ``pillarenv``.
    The value for matched pattern should be a string (that can use
    ``str.format`` syntax togetehr with captured variables from pattern)
    pointing to targe data center to use.

    If none patterns matched return ``None`` which meanse us datacenter of
    conencted Consul agent.
    '''
    log.debug("Resolving Consul datacenter based on: {dc}".format(dc=dc))

    try:
        mappings = dc.items()  # is it a dict?
    except AttributeError:
        log.debug('Using pre-defined DC: {dc!r}'.format(dc=dc))
        return dc

    log.debug(
        'Selecting DC based on pillarenv using {num} pattern(s)'.format(
            num=len(mappings)
        )
    )
    log.debug('Pillarenv set to {env!r}'.format(env=pillarenv))

    # sort in reverse based on pattern length
    # but use alphabetic order within groups of patterns of same length
    sorted_mappings = sorted(mappings, key=lambda m: (-len(m[0]), m[0]))

    for pattern, target in sorted_mappings:
        match = re.match(pattern, pillarenv)
        if match:
            log.debug('Matched pattern: {pattern!r}'.format(pattern=pattern))
            result = target.format(**match.groupdict())
            log.debug('Resolved datacenter: {result!r}'.format(result=result))
            return result

    log.debug(
        'None of following patterns matched pillarenv={env}: {lst}'.format(
            env=pillarenv, lst=', '.join(repr(x) for x in mappings)
        )
    )
