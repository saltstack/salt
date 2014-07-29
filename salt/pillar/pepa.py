#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
Configuration templating using Hierarchical substitution and Jinja.

Documentation: https://github.com/mickep76/pepa
'''

__author__ = 'Michael Persson <michael.ake.persson@gmail.com>'
__copyright__ = 'Copyright (c) 2013 Michael Persson'
__license__ = 'Apache License, Version 2.0'
__version__ = '0.6.3'

# Import python libs
import logging
import sys


# Only used when called from a TTY (terminal)
log = None
if __name__ == '__main__' and sys.stdout.isatty():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('hostname', help='Hostname')
    parser.add_argument('-c', '--config', default='/etc/salt/master', help='Configuration file')
    parser.add_argument('-d', '--debug', action='store_true', help='Print debug info')
    parser.add_argument('-g', '--grains', help='Input Grains as YAML')
    parser.add_argument('-p', '--pillar', help='Input Pillar as YAML')
    parser.add_argument('-n', '--no-color', action='store_true', help='No color output')
    args = parser.parse_args()

    LOG_LEVEL = logging.WARNING
    if args.debug:
        LOG_LEVEL = logging.DEBUG

    formatter = None
    if not args.no_color:
        try:
            import colorlog
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
    'pepa_subkey': False,
    'pepa_subkey_only': False
}

# Import libraries
import yaml
import jinja2
import re

try:
    from os.path import isfile, join
    HAS_OS_PATH = True
except ImportError:
    HAS_OS_PATH = False


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_OS_PATH:
        return False

    return True


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

    for categ, info in [s.items()[0] for s in sequence]:
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

# Only used when called from a TTY (terminal)
if __name__ == '__main__' and sys.stdout.isatty():
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

    yaml.dumper.SafeDumper.ignore_aliases = lambda self, data: True
    if not args.no_color:
        try:
            import pygments
            import pygments.lexers
            import pygments.formatters
            print pygments.highlight(yaml.safe_dump(result), pygments.lexers.YamlLexer(), pygments.formatters.TerminalFormatter())
        except ImportError:
            print yaml.safe_dump(result, indent=4, default_flow_style=False)
    else:
        print yaml.safe_dump(result, indent=4, default_flow_style=False)
