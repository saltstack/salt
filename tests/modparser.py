#!/usr/bin/env python2
'''
This script is used to list all python modules that are recursively imported
by all python files in a directory. For Salt this is use to obtain a list of
all non stdlib modules which are imported by all salt plugins
'''

import argparse
import os
import sys
import os
import modulefinder
import pprint


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
    out = parser.parse_args()
    return out.__dict__


def mod_data(opts, full):
    '''
    '''
    ret = {}
    finder = modulefinder.ModuleFinder()
    try:
        finder.load_file(full)
    except ImportError:
        sys.stderr.write('ImportError - {}\n'.format(full))
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
    '''
    ret = {}
    for root, dirs, files in os.walk(opts['root']):
        for fn_ in files:
            full = os.path.join(root, fn_)
            if full.endswith('.py'):
                ret.update(mod_data(opts, full))
    return ret


if __name__ == '__main__':
    opts = parse()
    pprint.pprint(scan(opts))
