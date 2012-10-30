#!/usr/bin/env python
'''
Test interacting with the wheel system. This script is useful when testing
wheel modules
'''

# Import Python libs
import optparse

# Import Salt Libs
import salt.config
import salt.wheel
import salt.auth


def parse():
    '''
    Parse the command line options
    '''
    parser = optparse.OptionParser()
    parser.add_option('-f',
            '--fun',
            '--function',
            dest='fun',
            help='The wheel function to execute')
    parser.add_option('-auth',
            '-a',
            dest='eauth',
            help='The external authentication mechanism to use')

    options, args = parser.parse_opts()

    cli = options.__dict__()

    for arg in args:
        if '=' in arg:
            comps = arg.split('=')
            cli[comps[0]] = comps[1]
    return cli


class Wheeler(object):
    '''
    Set up communication with the wheel interface
    '''
    def __init__(self, cli):
        self.cli = cli
        self.opts = salt.config.master_config('/etc/salt')
        self.wheel = salt.wheel.Wheel(self.opts)

    def _eauth(self):
        '''
        Fill in the blanks for the eauth system
        '''
        if self.cli['eauth']:
            res = resolver.cli(self.options.eauth)
        self.cli.update(res)

    def run(self):
        '''
        Execute the wheel call
        '''
        print wheel.master(self.cli['fun'], **self.cli)


if __name__ == '__main__':
    wheeler = Wheeler(parse())
    wheeler.run()
