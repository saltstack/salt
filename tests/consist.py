# -*- coding: utf-8 -*-

from __future__ import print_function
import yaml
import subprocess
import hashlib
import pprint
import optparse

BLACK = '\033[0;30m'
DARK_GRAY = '\033[1;30m'
LIGHT_GRAY = '\033[0;37m'
BLUE = '\033[0;34m'
LIGHT_BLUE = '\033[1;34m'
GREEN = '\033[0;32m'
LIGHT_GREEN = '\033[1;32m'
CYAN = '\033[0;36m'
LIGHT_CYAN = '\033[1;36m'
RED = '\033[0;31m'
LIGHT_RED = '\033[1;31m'
PURPLE = '\033[0;35m'
LIGHT_PURPLE = '\033[1;35m'
BROWN = '\033[0;33m'
YELLOW = '\033[1;33m'
WHITE = '\033[1;37m'
DEFAULT_COLOR = '\033[00m'
RED_BOLD = '\033[01;31m'
ENDC = '\033[0m'


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
            help='Specify the number of times to fun the consistency check')
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
    for key, val in data.items():
        has = hashlib.md5(str(val)).hexdigest()
        if has not in hashes:
            print('{0}:'.format(has))
            pprint.pprint(val)
        hashes.add(has)
    if len(hashes) > 1:
        print('{0}Command: {1} gave inconsistent returns{2}'.format(
            RED,
            command,
            ENDC,
            ))


if __name__ == '__main__':
    opts = parse()
    for _ in opts['runs']:
        for command in opts['command'].split(','):
            print('-' * 30)
            print('Running command {0}'.format(command))
            run(command)
