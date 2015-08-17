# -*- coding: utf-8 -*-
#!/usr/bin/env python2

from __future__ import absolute_import, print_function
try:
    import argparse  # pylint: disable=minimum-python-version
    HAS_ARGPARSE = True
except ImportError:
    HAS_ARGPARSE = False
import os
import sys
import os
import modulefinder
import pprint
import yaml
import json


def parse():
    '''
    Parse the arguments
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument(
            '-r',
            '--root',
            dest='root',
            default='.',
            help='The base code directory to look in')
    parser.add_argument(
            '-i',
            '--bif',
            dest='bif',
            default='site-packages')
    parser.add_argument(
            '-f',
            '--format',
            dest='format',
            choices=('pprint', 'yaml'),
            default='pprint')
    out = parser.parse_args()
    return out.__dict__


def mod_data(opts, full):
    '''
    Grab the module's data
    '''
    ret = {}
    finder = modulefinder.ModuleFinder()
    try:
        finder.load_file(full)
    except ImportError as exc:
        print('ImportError - {0} (Reason: {1})'.format(full, exc), file=sys.stderr)
        return ret
    for name, mod in finder.modules.items():
        basemod = name.split('.')[0]
        if basemod in ret:
            continue
        if basemod.startswith('_'):
            continue
        if not mod.__file__:
            continue
        if opts['bif'] not in mod.__file__:
            # Bif - skip
            continue
        if name == os.path.basename(mod.__file__)[:-3]:
            continue
        ret[basemod] = mod.__file__
    for name, err in finder.badmodules.items():
        basemod = name.split('.')[0]
        if basemod in ret:
            continue
        if basemod.startswith('_'):
            continue
        ret[basemod] = err
    return ret


def scan(opts):
    '''
    Scan the provided root for python source files
    '''
    ret = {}
    for root, dirs, files in os.walk(opts['root']):
        for fn_ in files:
            full = os.path.join(root, fn_)
            if full.endswith('.py'):
                ret.update(mod_data(opts, full))
    return ret


if __name__ == '__main__':
    if not HAS_ARGPARSE:
        print('The argparse python module is required')
    opts = parse()
    try:
        scand = scan(opts)
        if opts['format'] == 'yaml':
            print(yaml.dump(scand))
        if opts['format'] == 'json':
            print(json.dumps(scand))
        else:
            pprint.pprint(scand)
        exit(0)
    except KeyboardInterrupt:
        print('\nInterrupted on user request', file=sys.stderr)
        exit(1)
