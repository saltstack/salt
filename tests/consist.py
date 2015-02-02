# -*- coding: utf-8 -*-

# Import Python libs
from __future__ import absolute_import, print_function
import subprocess
import hashlib
import pprint
import optparse

# Import Salt libs
from salt.utils import get_colors

# Import 3rd-party libs
import yaml
import salt.ext.six as six

colors = get_colors()


def parse():
    '''
    Parse command line options
    '''
    parser = optparse.OptionParser()
    parser.add_option('-r',
            '--runs',
            dest='runs',
            default=10,
            type=int,
            help='Specify the number of times to run the consistency check')
    parser.add_option('-c',
            '--command',
            dest='command',
            default='state.show_highstate',
            help='The command to execute')

    options, args = parser.parse_args()
    return options.__dict__


def run(command):
    '''
    Execute a single command and check the returns
    '''
    cmd = r'salt \* {0} --yaml-out -t 500 > high'.format(command)
    subprocess.call(cmd, shell=True)
    data = yaml.load(open('high'))
    hashes = set()
    for key, val in six.iteritems(data):
        has = hashlib.md5(str(val)).hexdigest()
        if has not in hashes:
            print('{0}:'.format(has))
            pprint.pprint(val)
        hashes.add(has)
    if len(hashes) > 1:
        print('{0}Command: {1} gave inconsistent returns{2}'.format(
            colors['LIGHT_RED'],
            command,
            colors['ENDC']
            ))


if __name__ == '__main__':
    opts = parse()
    for _ in opts['runs']:
        for command in opts['command'].split(','):
            print('-' * 30)
            print('Running command {0}'.format(command))
            run(command)
