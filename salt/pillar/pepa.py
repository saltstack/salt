#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Pepa
====

Configuration templating for SaltStack using Hierarchical substitution and Jinja.

Configuring Pepa
================

.. code-block:: yaml

    extension_modules: /srv/salt/ext

    ext_pillar:
      - pepa:
          resource: host                # Name of resource directory and sub-key in pillars
          sequence:                     # Sequence used for hierarchical substitution
            - hostname:                 # Name of key
                name: input             # Alias used for template directory
                base_only: True         # Only use templates from Base environment, i.e. no staging
            - default:
            - environment:
            - location..region:
                name: region
            - location..country:
                name: country
            - location..datacenter:
                name: datacenter
            - roles:
            - osfinger:
                name: os
            - hostname:
                name: override
                base_only: True
          subkey: True                  # Create a sub-key in pillars, named after the resource in this case [host]
          subkey_only: True             # Only create a sub-key, and leave the top level untouched

    pepa_roots:                         # Base directory for each environment
      base: /srv/pepa/base              # Path for base environment
      dev: /srv/pepa/base               # Associate dev with base
      qa: /srv/pepa/qa
      prod: /srv/pepa/prod

    # Use a different delimiter for nested dictionaries, defaults to '..' since some keys may use '.' in the name
    #pepa_delimiter: ..

    # Supply Grains for Pepa, this should **ONLY** be used for testing or validation
    #pepa_grains:
    #  environment: dev

    # Supply Pillar for Pepa, this should **ONLY** be used for testing or validation
    #pepa_pillars:
    #  saltversion: 0.17.4

    # Enable debug for Pepa, and keep Salt on warning
    #log_level: debug

    #log_granular_levels:
    #  salt: warning
    #  salt.loaded.ext.pillar.pepa: debug

Pepa can also be used in Master-less SaltStack setup.

Command line
============

.. code-block:: bash

    usage: pepa.py [-h] [-c CONFIG] [-d] [-g GRAINS] [-p PILLAR] [-n] [-v]
                   hostname

    positional arguments:
      hostname              Hostname

    optional arguments:
      -h, --help            show this help message and exit
      -c CONFIG, --config CONFIG
                            Configuration file
      -d, --debug           Print debug info
      -g GRAINS, --grains GRAINS
                            Input Grains as YAML
      -p PILLAR, --pillar PILLAR
                            Input Pillar as YAML
      -n, --no-color        No color output
      -v, --validate        Validate output

Templates
=========

Templates is configuration for a host or software, that can use information from Grains or Pillars. These can then be used for hierarchically substitution.

**Example File:** host/input/test_example_com.yaml

.. code-block:: yaml

    location..region: emea
    location..country: nl
    location..datacenter: foobar
    environment: dev
    roles:
      - salt.master
    network..gateway: 10.0.0.254
    network..interfaces..eth0..hwaddr: 00:20:26:a1:12:12
    network..interfaces..eth0..dhcp: False
    network..interfaces..eth0..ipv4: 10.0.0.3
    network..interfaces..eth0..netmask: 255.255.255.0
    network..interfaces..eth0..fqdn: {{ hostname }}
    cobbler..profile: fedora-19-x86_64

As you see in this example you can use Jinja directly inside the template.

**Example File:** host/region/amer.yaml

.. code-block:: yaml

    network..dns..servers:
      - 10.0.0.1
      - 10.0.0.2
    time..ntp..servers:
      - ntp1.amer.example.com
      - ntp2.amer.example.com
      - ntp3.amer.example.com
    time..timezone: America/Chihuahua
    yum..mirror: yum.amer.example.com

Each template is named after the value of the key using lowercase and all extended characters are replaced with underscore.

**Example:**

osfinger: Fedora-19

**Would become:**

fedora_19.yaml

Nested dictionaries
===================

In order to create nested dictionaries as output you can use double dot **".."** as a delimiter. You can change this using "pepa_delimiter" we choose double dot since single dot is already used by key names in some modules, and using ":" requires quoting in the YAML.

**Example:**

.. code-block:: yaml

    network..dns..servers:
      - 10.0.0.1
      - 10.0.0.2
    network..dns..options:
      - timeout:2
      - attempts:1
      - ndots:1
    network..dns..search:
      - example.com

**Would become:**

.. code-block:: yaml

    network:
      dns:
        servers:
          - 10.0.0.1
          - 10.0.0.2
        options:
          - timeout:2
          - attempts:1
          - ndots:1
        search:
          - example.com

Operators
=========

Operators can be used to merge/unset a list/hash or set the key as immutable, so it can't be changed.

=========== ================================================
Operator    Description
=========== ================================================
merge()     Merge list or hash
unset()     Unset key
immutable() Set the key as immutable, so it can't be changed
imerge()    Set immutable and merge
iunset()    Set immutable and unset
=========== ================================================

**Example:**

.. code-block:: yaml

    network..dns..search..merge():
      - foobar.com
      - dummy.nl
    owner..immutable(): Operations
    host..printers..unset():

Validation
==========

Since it's very hard to test Jinja as is, the best approach is to run all the permutations of input and validate the output, i.e. Unit Testing.

To facilitate this in Pepa we use YAML, Jinja and Cerberus <https://github.com/nicolaiarocci/cerberus>.

Schema
======

So this is a validation schema for network configuration, as you see it can be customized with Jinja just as Pepa templates.

This was designed to be run as a build job in Jenkins or similar tool. You can provide Grains/Pillar input using either the config file or command line arguments.

**File Example: host/validation/network.yaml**

.. code-block:: yaml

    network..dns..search:
      type: list
      allowed:
        - example.com

    network..dns..options:
      type: list
      allowed: ['timeout:2', 'attempts:1', 'ndots:1']

    network..dns..servers:
      type: list
      schema:
        regex: ^([0-9]{1,3}\\.){3}[0-9]{1,3}$

    network..gateway:
      type: string
      regex: ^([0-9]{1,3}\\.){3}[0-9]{1,3}$

    {% if network.interfaces is defined %}
    {% for interface in network.interfaces %}

    network..interfaces..{{ interface }}..dhcp:
      type: boolean

    network..interfaces..{{ interface }}..fqdn:
      type: string
      regex: ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-zA-Z]{2,6}$

    network..interfaces..{{ interface }}..hwaddr:
      type: string
      regex: ^([0-9a-f]{1,2}\\:){5}[0-9a-f]{1,2}$

    network..interfaces..{{ interface }}..ipv4:
      type: string
      regex: ^([0-9]{1,3}\\.){3}[0-9]{1,3}$

    network..interfaces..{{ interface }}..netmask:
      type: string
      regex: ^([0-9]{1,3}\\.){3}[0-9]{1,3}$

    {% endfor %}
    {% endif %}

Links
=====

For more examples and information see <https://github.com/mickep76/pepa>.
'''

# Import futures
from __future__ import absolute_import, print_function

__author__ = 'Michael Persson <michael.ake.persson@gmail.com>'
__copyright__ = 'Copyright (c) 2013 Michael Persson'
__license__ = 'Apache License, Version 2.0'
__version__ = '0.6.6'

# Import python libs
import logging
import sys
import glob
import yaml
import jinja2
import re
from os.path import isfile, join

# Import 3rd-party libs
import salt.ext.six as six
from salt.ext.six.moves import input  # pylint: disable=import-error,redefined-builtin

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Import Salt libs
import salt.utils

# Only used when called from a terminal
log = None
if __name__ == '__main__':
    import argparse  # pylint: disable=minimum-python-version

    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', help='Hostname')
    parser.add_argument('-c', '--config', default='/etc/salt/master', help='Configuration file')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug info')
    parser.add_argument('-g', '--grains', help='Input Grains as YAML')
    parser.add_argument('-p', '--pillar', help='Input Pillar as YAML')
    parser.add_argument('-n', '--no-color', action='store_true', help='No color output')
    parser.add_argument('-v', '--validate', action='store_true', help='Validate output')
    parser.add_argument('-q', '--query-api', action='store_true', help='Query Saltstack REST API for Grains')
    parser.add_argument('--url', default='https://salt:8000', help='URL for SaltStack REST API')
    parser.add_argument('-u', '--username', help='Username for SaltStack REST API')
    parser.add_argument('-P', '--password', help='Password for SaltStack REST API')
    args = parser.parse_args()

    LOG_LEVEL = logging.WARNING
    if args.debug:
        LOG_LEVEL = logging.DEBUG

    formatter = None
    if not args.no_color:
        try:
            import colorlog  # pylint: disable=import-error
            formatter = colorlog.ColoredFormatter("[%(log_color)s%(levelname)-8s%(reset)s] %(log_color)s%(message)s%(reset)s")
        except ImportError:
            formatter = logging.Formatter("[%(levelname)-8s] %(message)s")
    else:
        formatter = logging.Formatter("[%(levelname)-8s] %(message)s")

    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)

    log = logging.getLogger('pythonConfig')
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)
else:
    log = logging.getLogger(__name__)


# Options
__opts__ = {
    'pepa_roots': {
        'base': '/srv/salt'
    },
    'pepa_delimiter': '..',
    'pepa_validate': False
}


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_REQUESTS:
        return False

    return True


def key_value_to_tree(data):
    '''
    Convert key/value to tree
    '''
    tree = {}
    for flatkey, value in six.iteritems(data):
        t = tree
        keys = flatkey.split(__opts__['pepa_delimiter'])
        for key in keys:
            if key == keys[-1]:
                t[key] = value
            else:
                t = t.setdefault(key, {})
    return tree


def ext_pillar(minion_id, pillar, resource, sequence, subkey=False, subkey_only=False):
    '''
    Evaluate Pepa templates
    '''
    roots = __opts__['pepa_roots']

    # Default input
    inp = {}
    inp['default'] = 'default'
    inp['hostname'] = minion_id

    if 'environment' in pillar:
        inp['environment'] = pillar['environment']
    elif 'environment' in __grains__:
        inp['environment'] = __grains__['environment']
    else:
        inp['environment'] = 'base'

    # Load templates
    output = inp
    output['pepa_templates'] = []
    immutable = {}

    for categ, info in [next(six.iteritems(s)) for s in sequence]:
        if categ not in inp:
            log.warn("Category is not defined: {0}".format(categ))
            continue

        alias = None
        if isinstance(info, dict) and 'name' in info:
            alias = info['name']
        else:
            alias = categ

        templdir = None
        if info and 'base_only' in info and info['base_only']:
            templdir = join(roots['base'], resource, alias)
        else:
            templdir = join(roots[inp['environment']], resource, alias)

        entries = []
        if isinstance(inp[categ], list):
            entries = inp[categ]
        elif not inp[categ]:
            log.warn("Category has no value set: {0}".format(categ))
            continue
        else:
            entries = [inp[categ]]

        for entry in entries:
            results_jinja = None
            results = None
            fn = join(templdir, re.sub(r'\W', '_', entry.lower()) + '.yaml')
            if isfile(fn):
                log.info("Loading template: {0}".format(fn))
                with salt.utils.fopen(fn) as fhr:
                    template = jinja2.Template(fhr.read())
                output['pepa_templates'].append(fn)

                try:
                    data = key_value_to_tree(output)
                    data['grains'] = __grains__.copy()
                    data['pillar'] = pillar.copy()
                    results_jinja = template.render(data)
                    results = yaml.load(results_jinja)
                except jinja2.UndefinedError as err:
                    log.error('Failed to parse JINJA template: {0}\n{1}'.format(fn, err))
                except yaml.YAMLError as err:
                    log.error('Failed to parse YAML in template: {0}\n{1}'.format(fn, err))
            else:
                log.info("Template doesn't exist: {0}".format(fn))
                continue

            if results is not None:
                for key in results:
                    skey = key.rsplit(__opts__['pepa_delimiter'], 1)
                    rkey = None
                    operator = None
                    if len(skey) > 1 and key.rfind('()') > 0:
                        rkey = skey[0].rstrip(__opts__['pepa_delimiter'])
                        operator = skey[1]

                    if key in immutable:
                        log.warning('Key {0} is immutable, changes are not allowed'.format(key))
                    elif rkey in immutable:
                        log.warning("Key {0} is immutable, changes are not allowed".format(rkey))
                    elif operator == 'merge()' or operator == 'imerge()':
                        if operator == 'merge()':
                            log.debug("Merge key {0}: {1}".format(rkey, results[key]))
                        else:
                            log.debug("Set immutable and merge key {0}: {1}".format(rkey, results[key]))
                            immutable[rkey] = True
                        if rkey not in output:
                            log.error('Cant\'t merge key {0} doesn\'t exist'.format(rkey))
                        elif not isinstance(results[key], type(output[rkey])):
                            log.error('Can\'t merge different types for key {0}'.format(rkey))
                        elif isinstance(results[key], dict):
                            output[rkey].update(results[key])
                        elif isinstance(results[key], list):
                            output[rkey].extend(results[key])
                        else:
                            log.error('Unsupported type need to be list or dict for key {0}'.format(rkey))
                    elif operator == 'unset()' or operator == 'iunset()':
                        if operator == 'unset()':
                            log.debug("Unset key {0}".format(rkey))
                        else:
                            log.debug("Set immutable and unset key {0}".format(rkey))
                            immutable[rkey] = True
                        if rkey in output:
                            del output[rkey]
                    elif operator == 'immutable()':
                        log.debug("Set immutable and substitute key {0}: {1}".format(rkey, results[key]))
                        immutable[rkey] = True
                        output[rkey] = results[key]
                    elif operator is not None:
                        log.error('Unsupported operator {0}, skipping key {1}'.format(operator, rkey))
                    else:
                        log.debug("Substitute key {0}: {1}".format(key, results[key]))
                        output[key] = results[key]

    tree = key_value_to_tree(output)
    pillar_data = {}
    if subkey_only:
        pillar_data[resource] = tree.copy()
    elif subkey:
        pillar_data = tree
        pillar_data[resource] = tree.copy()
    else:
        pillar_data = tree
    if __opts__['pepa_validate']:
        pillar_data['pepa_keys'] = output.copy()
    return pillar_data


def validate(output, resource):
    '''
    Validate Pepa templates
    '''
    try:
        import cerberus  # pylint: disable=import-error
    except ImportError:
        log.critical('You need module cerberus in order to use validation')
        return

    roots = __opts__['pepa_roots']

    valdir = join(roots['base'], resource, 'validate')

    all_schemas = {}
    pepa_schemas = []
    for fn in glob.glob(valdir + '/*.yaml'):
        log.info("Loading schema: {0}".format(fn))
        with salt.utils.fopen(fn) as fhr:
            template = jinja2.Template(fhr.read())
        data = output
        data['grains'] = __grains__.copy()
        data['pillar'] = __pillar__.copy()
        schema = yaml.load(template.render(data))
        all_schemas.update(schema)
        pepa_schemas.append(fn)

    val = cerberus.Validator()
    if not val.validate(output['pepa_keys'], all_schemas):
        for ekey, error in six.iteritems(val.errors):
            log.warning('Validation failed for key {0}: {1}'.format(ekey, error))

    output['pepa_schema_keys'] = all_schemas
    output['pepa_schemas'] = pepa_schemas


# Only used when called from a terminal
if __name__ == '__main__':
    # Load configuration file
    if not isfile(args.config):
        log.critical("Configuration file doesn't exist: {0}".format(args.config))
        sys.exit(1)

    # Get configuration
    with salt.utils.fopen(args.config) as fh_:
        __opts__.update(yaml.load(fh_.read()))

    loc = 0
    for name in [next(iter(list(e.keys()))) for e in __opts__['ext_pillar']]:
        if name == 'pepa':
            break
        loc += 1

    # Get grains
    __grains__ = {}
    if 'pepa_grains' in __opts__:
        __grains__ = __opts__['pepa_grains']
    if args.grains:
        __grains__.update(yaml.load(args.grains))

    # Get pillars
    __pillar__ = {}
    if 'pepa_pillar' in __opts__:
        __pillar__ = __opts__['pepa_pillar']
    if args.pillar:
        __pillar__.update(yaml.load(args.pillar))

    # Validate or not
    if args.validate:
        __opts__['pepa_validate'] = True

    if args.query_api:
        import requests
        import getpass

        username = args.username
        password = args.password
        if username is None:
            username = input('Username: ')
        if password is None:
            password = getpass.getpass()

        log.info('Authenticate REST API')
        auth = {'username': username, 'password': password, 'eauth': 'pam'}
        request = requests.post(args.url + '/login', auth)

        if not request.ok:
            raise RuntimeError('Failed to authenticate to SaltStack REST API: {0}'.format(request.text))

        response = request.json()
        token = response['return'][0]['token']

        log.info('Request Grains from REST API')
        headers = {'X-Auth-Token': token, 'Accept': 'application/json'}
        request = requests.get(args.url + '/minions/' + args.hostname, headers=headers)

        result = request.json().get('return', [{}])[0]
        if args.hostname not in result:
            raise RuntimeError('Failed to get Grains from SaltStack REST API')

        __grains__ = result[args.hostname]
#        print yaml.safe_dump(__grains__, indent=4, default_flow_style=False)

    # Print results
    ex_subkey = False
    ex_subkey_only = False
    if 'subkey' in __opts__['ext_pillar'][loc]['pepa']:
        ex_subkey = __opts__['ext_pillar'][loc]['pepa']['subkey']
    if 'subkey_only' in __opts__['ext_pillar'][loc]['pepa']:
        ex_subkey_only = __opts__['ext_pillar'][loc]['pepa']['subkey_only']

    result = ext_pillar(args.hostname, __pillar__, __opts__['ext_pillar'][loc]['pepa']['resource'],
                        __opts__['ext_pillar'][loc]['pepa']['sequence'], ex_subkey, ex_subkey_only)

    if __opts__['pepa_validate']:
        validate(result, __opts__['ext_pillar'][loc]['pepa']['resource'])

    yaml.dumper.SafeDumper.ignore_aliases = lambda self, data: True
    if not args.no_color:
        try:
            # pylint: disable=import-error
            import pygments
            import pygments.lexers
            import pygments.formatters
            # pylint: disable=no-member
            print(pygments.highlight(yaml.safe_dump(result),
                                     pygments.lexers.YamlLexer(),
                                     pygments.formatters.TerminalFormatter()))
            # pylint: enable=no-member, import-error
        except ImportError:
            print(yaml.safe_dump(result, indent=4, default_flow_style=False))
    else:
        print(yaml.safe_dump(result, indent=4, default_flow_style=False))
