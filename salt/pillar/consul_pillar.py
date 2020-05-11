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

The ``consul.token`` requires python-consul >= 0.4.7.

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
      - consul: my_consul_config root=salt

Using these configuration profiles, multiple consul sources may also be used:

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config
      - consul: my_other_consul_config

Either the ``minion_id``, or the ``role``, or the ``environment`` grain  may be used in the ``root``
path to expose minion-specific information stored in consul.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config root=salt/%(minion_id)s
      - consul: my_consul_config root=salt/%(role)s
      - consul: my_consul_config root=salt/%(environment)s

Minion-specific values may override shared values when the minion-specific root
appears after the shared root:

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config root=salt-shared
      - consul: my_other_consul_config root=salt-private/%(minion_id)s

If using the ``role`` or ``environment`` grain in the consul key path, be sure to define it using
`/etc/salt/grains`, or similar:

.. code-block:: yaml

    role: my-minion-role
    environment: dev

It's possible to lock down where the pillar values are shared through minion
targeting. Note that double quotes ``"`` are required around the target value
and cannot be used inside the matching statement. See the section on Compound
Matchers for more examples.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config root=salt target="L@salt.example.com and G@osarch:x86_64"

The data from Consul can be merged into a nested key in Pillar.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config pillar_root=consul_data

By default, keys containing YAML data will be deserialized before being merged into Pillar.
This behavior can be disabled by setting ``expand_keys`` to ``false``.

.. code-block:: yaml

    ext_pillar:
      - consul: my_consul_config expand_keys=false

'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import re

from salt.exceptions import CommandExecutionError
from salt.utils.dictupdate import update as dict_merge
import salt.utils.minions
import salt.utils.yaml

# Import third party libs
try:
    import consul
    if not hasattr(consul, '__version__'):
        consul.__version__ = '0.1'  # Some packages has no version, and so this pillar crashes on access to it.
except ImportError:
    consul = None

__virtualname__ = 'consul'

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only return if python-consul is installed
    '''
    return __virtualname__ if consul is not None else False


def ext_pillar(minion_id,
               pillar,  # pylint: disable=W0613
               conf):
    '''
    Check consul for all data
    '''
    opts = {}
    temp = conf
    target_re = re.compile('target="(.*?)"')
    match = target_re.search(temp)
    if match:
        opts['target'] = match.group(1)
        temp = temp.replace(match.group(0), '')
        checker = salt.utils.minions.CkMinions(__opts__)
        _res = checker.check_minions(opts['target'], 'compound')
        minions = _res['minions']
        log.debug('Targeted minions: %r', minions)
        if minion_id not in minions:
            return {}

    root_re = re.compile('(?<!_)root=(\S*)')  # pylint: disable=W1401
    match = root_re.search(temp)
    if match:
        opts['root'] = match.group(1).rstrip('/')
        temp = temp.replace(match.group(0), '')
    else:
        opts['root'] = ""

    pillar_root_re = re.compile('pillar_root=(\S*)')  # pylint: disable=W1401
    match = pillar_root_re.search(temp)
    if match:
        opts['pillar_root'] = match.group(1).rstrip('/')
        temp = temp.replace(match.group(0), '')
    else:
        opts['pillar_root'] = ""

    profile_re = re.compile('(?:profile=)?(\S+)')  # pylint: disable=W1401
    match = profile_re.search(temp)
    if match:
        opts['profile'] = match.group(1)
        temp = temp.replace(match.group(0), '')
    else:
        opts['profile'] = None

    expand_keys_re = re.compile('expand_keys=False', re.IGNORECASE)  # pylint: disable=W1401
    match = expand_keys_re.search(temp)
    if match:
        opts['expand_keys'] = False
        temp = temp.replace(match.group(0), '')
    else:
        opts['expand_keys'] = True

    client = get_conn(__opts__, opts['profile'])

    role = __salt__['grains.get']('role', None)
    environment = __salt__['grains.get']('environment', None)
    # put the minion's ID in the path if necessary
    opts['root'] %= {
        'minion_id': minion_id,
        'role': role,
        'environment': environment
    }

    try:
        pillar_tree = fetch_tree(client, opts['root'], opts['expand_keys'])
        if opts['pillar_root']:
            log.debug('Merging consul path %s/ into pillar at %s/', opts['root'], opts['pillar_root'])

            pillar = {}
            branch = pillar
            keys = opts['pillar_root'].split('/')

            for i, k in enumerate(keys):
                if i == len(keys) - 1:
                    branch[k] = pillar_tree
                else:
                    branch[k] = {}
                    branch = branch[k]
        else:
            pillar = pillar_tree
    except KeyError:
        log.error('No such key in consul profile %s: %s', opts['profile'], opts['root'])
        pillar = {}

    return pillar


def consul_fetch(client, path):
    '''
    Query consul for all keys/values within base path
    '''
    # Unless the root path is blank, it needs a trailing slash for
    # the kv get from Consul to work as expected
    return client.kv.get('' if not path else path.rstrip('/') + '/', recurse=True)


def fetch_tree(client, path, expand_keys):
    '''
    Grab data from consul, trim base path and remove any keys which
    are folders. Take the remaining data and send it to be formatted
    in such a way as to be used as pillar data.
    '''
    _, items = consul_fetch(client, path)
    ret = {}
    has_children = re.compile(r'/$')

    log.debug('Fetched items: %r', items)

    if items is None:
        return ret
    for item in reversed(items):
        key = re.sub(r'^' + re.escape(path) + '/?', '', item['Key'])
        if key != '':
            log.debug('path/key - %s: %s', path, key)
            log.debug('has_children? %r', has_children.search(key))
        if has_children.search(key) is None:
            ret = pillar_format(ret, key.split('/'), item['Value'], expand_keys)
            log.debug('Fetching subkeys for key: %r', item)

    return ret


def pillar_format(ret, keys, value, expand_keys):
    '''
    Perform data formatting to be used as pillar data and
    merge it with the current pillar data
    '''
    # if value is empty in Consul then it's None here - skip it
    if value is None:
        return ret

    # If value is not None then it's a string
    # YAML strips whitespaces unless they're surrounded by quotes
    # If expand_keys is true, deserialize the YAML data
    if expand_keys:
        pillar_value = salt.utils.yaml.safe_load(value)
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

    params = {}
    for key in conf:
        if key.startswith('consul.'):
            params[key.split('.')[1]] = conf[key]

    if 'dc' in params:
        pillarenv = opts_merged.get('pillarenv') or 'base'
        params['dc'] = _resolve_datacenter(params['dc'], pillarenv)

    if consul:
        # Sanity check. ACL Tokens are supported on python-consul 0.4.7 onwards only.
        if consul.__version__ < '0.4.7' and params.get('target'):
            params.pop('target')
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
    log.debug('Resolving Consul datacenter based on: %s', dc)

    try:
        mappings = dc.items()  # is it a dict?
    except AttributeError:
        log.debug('Using pre-defined DC: \'%s\'', dc)
        return dc

    log.debug('Selecting DC based on pillarenv using %d pattern(s)', len(mappings))
    log.debug('Pillarenv set to \'%s\'', pillarenv)

    # sort in reverse based on pattern length
    # but use alphabetic order within groups of patterns of same length
    sorted_mappings = sorted(mappings, key=lambda m: (-len(m[0]), m[0]))

    for pattern, target in sorted_mappings:
        match = re.match(pattern, pillarenv)
        if match:
            log.debug('Matched pattern: \'%s\'', pattern)
            result = target.format(**match.groupdict())
            log.debug('Resolved datacenter: \'%s\'', result)
            return result

    log.debug(
        'None of following patterns matched pillarenv=%s: %s',
        pillarenv, ', '.join(repr(x) for x in mappings)
    )
