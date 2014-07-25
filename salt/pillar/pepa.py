#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Configuration templating using Hierarchical substitution and Jinja.

Documentation: https://github.com/mickep76/pepa
'''

__author__ = 'Michael Persson <michael.ake.persson@gmail.com>'
__copyright__ = 'Copyright (c) 2013 Michael Persson'
__license__ = 'GPLv3'
__version__ = '0.6.2'

# Import python libs
import logging
import sys

log = None
if sys.stdout.isatty():
    import argparse
    from colorlog import ColoredFormatter

    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', help = 'Hostname')
    parser.add_argument('-c', '--config', default='/etc/salt/master', help='Configuration file')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug info')
    parser.add_argument('-g', '--grains', help='Input Grains as YAML')
    parser.add_argument('-p', '--pillar', help='Input Pillar as YAML')
    args = parser.parse_args()

    LOG_LEVEL = logging.WARNING
    if args.debug:
        LOG_LEVEL = logging.DEBUG

    LOG_FORMAT = "[%(log_color)s%(levelname)-8s%(reset)s] %(log_color)s%(message)s%(reset)s"
    formatter = ColoredFormatter(LOG_FORMAT)

    stream = logging.StreamHandler()
    stream.setLevel(LOG_LEVEL)
    stream.setFormatter(formatter)

    log = logging.getLogger('pythonConfig')
    log.setLevel(LOG_LEVEL)
    log.addHandler(stream)
else:
    log = logging.getLogger(__name__)

# Name
__virtualname__ = 'pepa'

# Options
__opts__ = {
    'pepa_roots': {
        'base': '/srv/salt'
    },
    'pepa_delimiter': '..',
    'pepa_subkey': False,
    'pepa_subkey_only': False
}

# Import libraries
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from os.path import isfile, join
    HAS_OS_PATH = True
except ImportError:
    HAS_OS_PATH = False

try:
    import re
    HAS_RE = True
except ImportError:
    HAS_RE = False

try:
    import jinja2
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_YAML:
        log.error('Failed to load "yaml" library')
        return False

    if not HAS_OS_PATH:
        log.error('Failed to load "os.path" library')
        return False

    if not HAS_RE:
        log.error('Failed to load "re" library')
        return False

    if not HAS_JINJA2:
        log.error('Failed to load "jinja2" library')
        return False

    return __virtualname__


def key_value_to_tree(data):
    '''
    Convert key/value to tree
    '''
    tree = {}
    for flatkey, value in data.items():
        t = tree
        keys = flatkey.split(__opts__['pepa_delimiter'])
        for key in keys:
            if key == keys[-1]:
                t[key] = value
            else:
                t = t.setdefault(key, {})
    return tree


def ext_pillar(minion_id, pillar, resource, sequence):
    '''
    Convert key/value to tree
    '''
    roots = __opts__['pepa_roots']

    # Default input
    input = {}
    input['default'] = 'default'
    input['hostname'] = minion_id

    if 'environment' in pillar:
        input['environment'] = pillar['environment']
    elif 'environment' in __grains__:
        input['environment'] = __grains__['environment']
    else:
        input['environment'] = 'base'

    # Load templates
    output = input
    output['pepa_templates'] = []

    for name, info in [s.items()[0] for s in sequence]:
        if name not in input:
            log.warn("Category is not defined: {0}".format(name))
            continue

        alias = None
        if type(info) is dict and 'name' in info:
            alias = info['name']
        else:
            alias = name

        templdir = None
        if info and 'base_only' in info and info['base_only']:
            templdir = join(roots['base'], resource, alias)
        else:
            templdir = join(roots[input['environment']], resource, alias)

        entries = []
        if type(input[name]) is list:
            entries = input[name]
        elif not input[name]:
            log.warn("Category has no value set: {0}".format(name))
            continue
        else:
            entries = [input[name]]

        for entry in entries:
            results = None
            fn = join(templdir, re.sub(r'\W', '_', entry.lower()) + '.yaml')
            if isfile(fn):
                log.info("Loading template: {0}".format(fn))
                template = jinja2.Template(open(fn).read())
                output['pepa_templates'].append(fn)
                data = key_value_to_tree(output)
                data['grains'] = __grains__.copy()
                data['pillar'] = pillar.copy()
                results = yaml.load(template.render(data))
            else:
                log.info("Template doesn't exist: {0}".format(fn))
                continue

            if results is not None:
                for key in results:
                    log.debug("Substituting key {0}: {1}".format(key, results[key]))
                    output[key] = results[key]

    tree = key_value_to_tree(output)
    pillar_data = {}
    if __opts__['pepa_subkey_only']:
        pillar_data['pepa'] = tree.copy()
    elif __opts__['pepa_subkey']:
        pillar_data = tree
        pillar_data['pepa'] = tree.copy()
    else:
        pillar_data = tree
    return pillar_data

if sys.stdout.isatty():
    # Load configuration file
    if not isfile(args.config):
        log.critical("Configuration file doesn't exist: {0}".format(args.config))
        sys.exit(1)

    # Get configuration
    __opts__.update(yaml.load(open(args.config).read()))

    loc = 0
    for name in [e.keys()[0] for e in __opts__['ext_pillar']]:
        if name == 'pepa':
            break
        loc += 1

    __grains__ = {}
    if 'pepa_grains' in __opts__:
        __grains__ = __opts__['pepa_grains']
    if args.grains:
        __grains__.update(yaml.load(args.grains))

    __pillar__ = {}
    if 'pepa_pillar' in __opts__:
        __pillar__ = __opts__['pepa_pillar']
    if args.pillar:
        __pillar__.update(yaml.load(args.pillar))

    result = ext_pillar(args.hostname, __pillar__, __opts__['ext_pillar'][loc]['pepa']['resource'], __opts__['ext_pillar'][loc]['pepa']['sequence'])

    from pygments import highlight
    from pygments.lexers import YamlLexer
    from pygments.formatters import TerminalFormatter

    yaml.dumper.SafeDumper.ignore_aliases = lambda self, data: True
#    print yaml.safe_dump(result, indent = 4, default_flow_style = False)
    print highlight(yaml.safe_dump(result), YamlLexer(), TerminalFormatter())
